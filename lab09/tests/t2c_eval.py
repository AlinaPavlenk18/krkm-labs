"""
ЛР9 · Результат 5 · Кроки 3–4. Оцінювання text-to-Cypher.

Для кожного питання: згенерований запит → t2c_guard.check (запис/схема/LIMIT) → виконання
→ порівняння з еталонним (gold) запитом. Запит коректний, якщо для КОЖНОЇ ключової колонки
еталону в результаті є колонка з тим самим мультимножинним набором значень (порядок рядків,
назви колонок і додаткові колонки не враховуються; числа — з допуском 0.01).

Рушії:
  --engine neo4j  (основний) — виконання від імені користувача з роллю reader
                   (NEO4J_T2C_USER / NEO4J_T2C_PASSWORD) у сесії READ_ACCESS з тайм-аутом 5 с;
  --engine kuzu   (контроль у середовищі підготовки) — вбудована Kùzu з автоматичними
                   діалектними замінами.
Вхід:  llm_log/t2c_*_raw.jsonl (сирий вихід LLM), tests/t2c_gold.json, tests/t2c_questions*.json
Вихід: tests/t2c_run.jsonl (по рядку на питання; зведений файл трьох прогонів — tests/t2c.jsonl) і метрика у stdout.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))
from t2c_guard import GuardError, check  


def to_kuzu(q):
    """Діалектні заміни Neo4j → Kùzu (лише синтаксис, семантика та сама)."""
    m = re.search(r"MATCH\s+\((\w+):(\w+)\s*(\{[^}]*\})\)\s*,\s*\((\w+):(\w+)\s*(\{[^}]*\})\)\s+"
                  r"MATCH\s+(\w+)\s*=\s*shortestPath\(\(\1\)-\[([^\]]*?)\*\.\.(\d+)\]-\(\4\)\)", q)
    if m:
        a, la, pa, b, lb, pb, p, types, n = m.groups()
        q = q.replace(m.group(0), f"MATCH {p} = ({a}:{la} {pa})-[{types}* SHORTEST 1..{n}]-({b}:{lb} {pb})")
    # форма «MATCH (a…), (b…), p = shortestPath((a)-[*]-(b))» (усе в одному MATCH)
    m = re.search(r"MATCH\s+\((\w+):(\w+)\s*(\{[^}]*\})\)\s*,\s*\((\w+):(\w+)\s*(\{[^}]*\})\)\s*,\s*"
                  r"(\w+)\s*=\s*shortestPath\(\(\1\)-\[([^\]]*?)\*(?:\.\.(\d+))?\]-\(\4\)\)", q)
    if m:
        a, la, pa, b, lb, pb, p, types, n = m.groups()
        q = q.replace(m.group(0), f"MATCH {p} = ({a}:{la} {pa})-[{types}* SHORTEST 1..{n or 30}]-({b}:{lb} {pb})")
    # reduce(t = 0.0, x IN L | t + x.prop) → list_sum(list_transform(L, x -> x.prop))
    q = re.sub(r"reduce\(\s*\w+\s*=\s*0(?:\.0)?\s*,\s*(\w+)\s+IN\s+(\w+)\s*\|\s*\w+\s*\+\s*\1\.(\w+)\s*\)",
               r"list_sum(list_transform(\2, v_ -> v_.\3))", q)
    q = re.sub(r"\[(\w+) IN nodes\((\w+)\) \| \1\.id\]", r"properties(nodes(\2), 'id')", q)
    q = re.sub(r"\[(\w+) IN relationships\((\w+)\) \| type\(\1\)\]", r"list_transform(rels(\2), r_ -> label(r_))", q)
    q = re.sub(r"\*(\d)\.\.\]", r"*\1..30]", q)
    q = re.sub(r"EXISTS\s*\{\s*\(", "EXISTS { MATCH (", q)
   
    for var, lst in re.findall(r"collect\(DISTINCT (\w+)\) AS (\w+)", q):
        m2 = re.search(r"WHERE (\w+) IN " + lst + r"\b", q)
        if m2:
            q = q.replace(f"collect(DISTINCT {var}) AS {lst}", f"collect(DISTINCT {var}.id) AS {lst}")
            q = q.replace(m2.group(0), f"WHERE {m2.group(1)}.id IN {lst}")
    q = q.replace("toFloat(", "to_double(")
    q = re.sub(r"localdatetime\(('[^']*')\)", r"timestamp(\1)", q)
    return q


class KuzuEngine:
    def __init__(self):
        import tempfile
        import verify_kuzu
        self.db, self.con = verify_kuzu.build(Path(tempfile.mkdtemp()) / "db")

    def run(self, q):
        res = self.con.execute(to_kuzu(q))
        cols = res.get_column_names()
        rows = []
        while res.has_next():
            rows.append(dict(zip(cols, res.get_next())))
        return rows


class Neo4jEngine:
    def __init__(self):
        import os
        from neo4j import READ_ACCESS, GraphDatabase, unit_of_work

        @unit_of_work(timeout=5.0)          
        def _read(tx, q):
            return [r.data() for r in tx.run(q)]
        self._read = _read
        self.drv = GraphDatabase.driver(os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
                                        auth=(os.environ["NEO4J_T2C_USER"], os.environ["NEO4J_T2C_PASSWORD"]))
        self.session = self.drv.session(database=os.environ.get("NEO4J_DATABASE", "neo4j"),
                                        default_access_mode=READ_ACCESS)

    def run(self, q):
        self.session.run("EXPLAIN " + q).consume()          
        return self.session.execute_read(self._read, q)

def norm(v):
    if isinstance(v, float):
        return round(v, 2)
    if hasattr(v, "iso_format"):
        return v.iso_format()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, list):
        return tuple(norm(x) for x in v)
    return v


def column(rows, c):
    return sorted((norm(r[c]) for r in rows), key=repr)


def close(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            if abs(x - y) > 0.01:
                return False
        elif x != y:
            return False
    return True


def compare(gold_rows, gen_rows, keys):
    if len(gold_rows) != len(gen_rows):
        return False, f"кількість рядків {len(gen_rows)} ≠ {len(gold_rows)}"
    if not gen_rows:
        return True, "обидва результати порожні"
    gen_cols = list(gen_rows[0].keys())
    for k in keys:
        g = column(gold_rows, k)
        if not any(close(g, column(gen_rows, c)) for c in gen_cols):
            return False, f"немає колонки, що збігається з еталонною «{k}»"
    return True, "збігається з еталоном"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["neo4j", "kuzu"], default="neo4j")
    ap.add_argument("--raw", nargs="+", default=sorted(str(p) for p in (ROOT / "llm_log").glob("t2c_*_raw.jsonl")))
    ap.add_argument("--out", default=str(HERE / "t2c_run.jsonl"))
    ap.add_argument("--model", default="claude-opus-5-5 (агент Claude, claude.ai)")
    args = ap.parse_args()

    gold = json.loads((HERE / "t2c_gold.json").read_text(encoding="utf-8"))
    questions = {}
    for f in HERE.glob("t2c_questions*.json"):
        for q in json.loads(f.read_text(encoding="utf-8")):
            questions[q["id"]] = q["question"]
    eng = KuzuEngine() if args.engine == "kuzu" else Neo4jEngine()

    results = []
    for raw in args.raw:
        for line in Path(raw).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            qid, gen = item["id"], item["cypher"]
            rec = {"id": qid, "question": questions.get(qid, ""), "model": item.get("model", args.model),
                   "prompt_version": item.get("prompt_version", "v1"), "generated": gen,
                   "gold": gold[qid]["cypher"], "engine": args.engine}
            try:
                safe, notes = check(gen)
                rec["guard"] = "ok" + (f" ({'; '.join(notes)})" if notes else "")
            except GuardError as e:
                rec.update(guard=f"blocked: {e}", correct=False, reason=f"відхилено захисним шаром: {e}")
                results.append(rec)
                continue
            try:
                t0 = time.perf_counter()
                gen_rows = eng.run(safe)
                rec["time_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                gold_rows = eng.run(gold[qid]["cypher"])
                ok, why = compare(gold_rows, gen_rows, gold[qid]["key"])
                rec.update(correct=ok, reason=why, rows=len(gen_rows), gold_rows=len(gold_rows),
                           result_sample=[{k: norm(v) for k, v in r.items()} for r in gen_rows[:5]])
            except Exception as e:  
                rec.update(correct=False, reason=f"помилка виконання: {str(e).splitlines()[0][:200]}")
            results.append(rec)

    with open(args.out, "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    n_ok = sum(r["correct"] for r in results)
    print(f"Коректних: {n_ok}/{len(results)} = {n_ok / len(results):.0%}")
    for r in results:
        print(f"  {r['id']}: {'OK ' if r['correct'] else 'ERR'} {r.get('guard', '')} | {r['reason']}")


if __name__ == "__main__":
    main()