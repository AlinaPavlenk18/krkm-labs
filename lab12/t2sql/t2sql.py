"""Text-to-SQL із семантичним контекстом і захистами.

Конвеєр: питання → підказка (схема + метрики + значення атрибутів) → LLM (Ollama, локально)
→ AST-перевірка sqlglot (один SELECT, білий список таблиць, без файлових функцій) → LIMIT ≤ 200
→ EXPLAIN → виконання в read-only з'єднанні без зовнішнього доступу з тайм-аутом.
"""
import os, re, threading, time
from pathlib import Path
import duckdb, requests, sqlglot, yaml
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/warehouse.duckdb"
MODEL = os.getenv("T2SQL_MODEL", "qwen2.5:7b")
OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
MAX_ROWS, TIMEOUT_S = 200, 10
TABLES = {"fact_consumption", "dim_date", "dim_hour", "dim_consumer_class", "dim_consumer", "dim_substation"}
FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command,
             exp.Copy, exp.Set, exp.Pragma, exp.Merge, exp.TruncateTable, exp.Attach, exp.Detach, exp.Use)
FILE_FUNCS = re.compile(r"^(read_|glob$|sniff_csv|parquet_|query_table|query$|getenv)", re.I)


class Rejected(Exception):
    pass

def build_prompt() -> str:
    ddl = (ROOT / "sql/ddl.sql").read_text(encoding="utf-8")
    schema = "\n".join(l for l in ddl.splitlines() if l.strip() and not l.startswith("--"))
    spec = yaml.safe_load((ROOT / "semantic/metrics.yml").read_text(encoding="utf-8"))
    metrics = "\n".join(f"- {m['name']} ({m['label']}, {m['unit']}): {m['definition']} "
                        f"Формула: {m['formula']}. Обмеження: {m['constraints']}" for m in spec["metrics"])
    con = connect()
    vals = []
    for t, col in [("dim_consumer_class", "class_label"), ("dim_substation", "region_name"),
                   ("dim_substation", "substation_name"), ("dim_hour", "part_of_day"), ("dim_date", "day_name")]:
        v = [r[0] for r in con.execute(f"SELECT DISTINCT {col} FROM {t} ORDER BY 1").fetchall()]
        vals.append(f"- {t}.{col}: {', '.join(map(str, v))}")
    vals.append("- dim_consumer.consumer_id: формат 'Consumer_3310'; fact_consumption.meter_id: формат 'Meter_AMI10452'")
    vals.append("- dim_hour.is_peak = TRUE для годин 8–10 і 18–21; дати: 2026-01-01 … 2026-01-31")
    con.close()
    tpl = (ROOT / "prompts/t2sql_v1.md").read_text(encoding="utf-8")
    return tpl.format(schema=schema, metrics=metrics, values="\n".join(vals))


def generate(question: str, system: str) -> dict:
    t0 = time.time()
    r = requests.post(f"{OLLAMA}/api/chat", timeout=600, json={
        "model": MODEL, "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 400},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}]})
    r.raise_for_status()
    j = r.json()
    raw = j["message"]["content"]
    m = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.S | re.I)
    return {"raw": raw, "sql": (m.group(1) if m else raw).strip(),
            "prompt_tokens": j.get("prompt_eval_count", 0), "completion_tokens": j.get("eval_count", 0),
            "latency_s": round(time.time() - t0, 2)}


def guard(sql: str) -> str:
    try:
        stmts = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise Rejected(f"не вдалося розібрати SQL: {str(e)[:120]}")
    if len(stmts) != 1:
        raise Rejected(f"очікувався 1 запит, отримано {len(stmts)}")
    tree = stmts[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise Rejected(f"дозволено лише SELECT, отримано {type(tree).__name__}")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN):
            raise Rejected(f"заборонений вузол {type(node).__name__}")
        if isinstance(node, exp.Func):
            fname = node.sql_name() if not isinstance(node, exp.Anonymous) else node.name
            if FILE_FUNCS.match(fname or ""):
                raise Rejected(f"заборонена функція {fname}")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        if not t.name:
            raise Rejected("табличний вираз замість таблиці")
        if t.name.lower() not in TABLES | ctes:
            raise Rejected(f"таблиця поза білим списком: {t.name}")
    lim = tree.args.get("limit")
    n = None
    if lim is not None:
        try:
            n = int(lim.expression.name)
        except (AttributeError, ValueError):
            n = None
    if n is None or n > MAX_ROWS:
        tree = tree.limit(MAX_ROWS)
    return tree.sql(dialect="duckdb")


def connect():
    return duckdb.connect(str(DB), read_only=True,
                          config={"enable_external_access": False, "lock_configuration": True})


def execute(sql: str, timeout_s: int = TIMEOUT_S):
    con = connect()
    try:
        con.execute(f"EXPLAIN {sql}")              # прив'язка імен і план без виконання
        timer = threading.Timer(timeout_s, con.interrupt)
        timer.start()
        try:
            return con.execute(sql).df()
        finally:
            timer.cancel()
    finally:
        con.close()


def ask(question: str, system: str | None = None, sql_override: str | None = None) -> dict:
    """Повний конвеєр. sql_override — для самоперевірки без LLM (режим --engine gold)."""
    rec = {"question": question}
    if sql_override is None:
        rec.update(generate(question, system or build_prompt()))
    else:
        rec.update({"raw": sql_override, "sql": sql_override, "prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0})
    try:
        rec["final_sql"] = guard(rec["sql"])
        rec["guard"] = "passed"
    except Rejected as e:
        rec.update({"final_sql": None, "guard": f"rejected: {e}", "result": None, "error": None})
        return rec
    try:
        df = execute(rec["final_sql"])
        rec.update({"result": df, "error": None})
    except Exception as e: 
        rec.update({"result": None, "error": f"{type(e).__name__}: {str(e)[:200]}"})
    return rec


if __name__ == "__main__":
    import sys
    out = ask(" ".join(sys.argv[1:]) or "Скільки енергії спожили побутові споживачі?")
    print(out["final_sql"] or out["guard"])
    print(out["result"] if out.get("result") is not None else out.get("error"))
