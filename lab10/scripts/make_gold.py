"""Збирає золотий набір eval/gold.jsonl (Результат 5, крок 1).

Джерела запитів:
  eval/gold_candidates_llm.jsonl — кандидати, згенеровані LLM лише за документами рівнів public/internal
                                   (і запити без відповіді); їх переглядає людина (eval/gold_review.csv);
  шаблонні запити (тут, функція template_queries) — для документів рівня restricted: за політикою kb10
                                   їхній текст не передається в зовнішню LLM, тому запити й докази
                                   сформовано детерміновано з даних графа.
Рішення рецензента читаються з eval/gold_review.csv (колонка decision: accept / reject / edit).
Для edit виправлення вносяться у gold_candidates_llm.jsonl вручну, а decision ставиться accept.

Перевірки: кожен доказ має бути дослівно (після нормалізації) присутній у своєму документі
(data/clean/docs.jsonl); запити підмножин R2 (10) і R3 (20) позначаються полями r2 / r3.
Запуск: python scripts/make_gold.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import CLEAN, DATA, EVAL, normalize, read_jsonl, write_jsonl  # noqa: E402

R2_SET = ["q01", "q03", "q11", "q14", "q15", "q17", "q20", "q34", "q36", "q42"]
R3_SET = R2_SET + ["q05", "q21", "q24", "q26", "q28", "q29", "q30", "q31", "q32", "q38"]


def template_queries():
    import csv as _csv
    src = DATA / "source" / "lab09_graph"
    rd = lambda n: list(_csv.DictReader(open(src / n, encoding="utf-8")))
    cons = {r["id"]: r for r in rd("nodes_consumer.csv")}
    managed = {r["end"] for r in rd("rels_manages.csv")}
    conn = rd("rels_connected_to.csv")
    hm = rd("rels_has_meter.csv")
    num = lambda x: f"{float(x):.1f}".rstrip("0").rstrip(".").replace(".", ",")
    out = []
    # T1: споживач з найбільшим лімітом на підстанції без диспетчера
    unmanaged = sorted({r["end"] for r in conn} - managed)
    for s in unmanaged:
        cs = [r["start"] for r in conn if r["end"] == s]
        top = max(cs, key=lambda c: float(cons[c]["contractLimit"]))
        n = top.split("_")[1]
        out.append({"qid": "q39", "qtype": "multihop", "lang": "uk", "source": "template",
                    "query": "Який споживач на підстанції без диспетчера має найбільший договірний ліміт і яка його адреса?",
                    "answerable": True, "relevant": [
                        {"doc_id": "gen03", "evidence": f"Споживач №{n} — {cons[top]['category']}, адреса: {cons[top]['address']}", "grade": 2},
                        {"doc_id": "kb06", "evidence": f"Підстанція №{s.split('_')[1]} у Закарпатській області не має призначеного диспетчера", "grade": 1}]})
    # T2: адреса й підстанція конкретного споживача (ЛР8)
    c = "Consumer_4521"
    sub = next(r["end"] for r in conn if r["start"] == c)
    out.append({"qid": "q40", "qtype": "keyword", "lang": "uk", "source": "template",
                "query": "Яка адреса споживача №4521 і до якої підстанції він підключений?", "answerable": True,
                "relevant": [{"doc_id": "gen03", "evidence": f"Споживач №4521 — {cons[c]['category']}, адреса: {cons[c]['address']}", "grade": 2},
                             {"doc_id": "kb12", "evidence": f"промисловий №4521 (450 кВт) на №{sub.split('_')[1]}", "grade": 1}]})
    # T3: лічильники споживача з двома вводами
    c = "Consumer_5038"
    ms = [r["end"] for r in hm if r["start"] == c]
    out.append({"qid": "q41", "qtype": "keyword", "lang": "uk", "source": "template",
                "query": "Які лічильники встановлено в споживача №5038?", "answerable": True,
                "relevant": [{"doc_id": "gen03", "evidence": f"Споживач №5038 — {cons[c]['category']}, адреса: {cons[c]['address']}. Договірний ліміт {num(cons[c]['contractLimit'])} кВт", "grade": 2},
                             {"doc_id": "kb05", "evidence": "має два лічильники", "grade": 1}]})
    return out


def load_review():
    p = EVAL / "gold_review.csv"
    if not p.exists():
        return {}
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:          # Excel «CSV (розділювач — кома)» у Windows зберігає в cp1251
        text = raw.decode("cp1251")
    first = text.splitlines()[0] if text else ""
    delim = ";" if first.count(";") > first.count(",") else ","   # українська локаль Excel пише «;»
    rows = csv.DictReader(text.splitlines(), delimiter=delim)
    return {r["qid"].strip(): {k.strip(): (v or "").strip() for k, v in r.items() if k} for r in rows}


def write_review_sheet(gold):
    p = EVAL / "gold_review.csv"
    if p.exists():
        return
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["qid", "qtype", "lang", "source", "query", "evidences", "decision", "comment"])
        for g in gold:
            ev = " || ".join(f"[{e['doc_id']}, {e['grade']}] {e['evidence']}" for e in g["relevant"]) or "— (без відповіді)"
            w.writerow([g["qid"], g["qtype"], g["lang"], g.get("source", "llm"), g["query"], ev, "", ""])


def main():
    docs = {d["doc_id"]: normalize(" ".join(s["text"] for s in d["sections"])) for d in read_jsonl(CLEAN / "docs.jsonl")}
    cand = read_jsonl(EVAL / "gold_candidates_llm.jsonl")
    for c in cand:
        c.setdefault("source", "llm")
    gold = sorted(cand + template_queries(), key=lambda g: int(g["qid"][1:]))
    write_review_sheet(gold)
    review = load_review()
    errors, kept = [], []
    for g in gold:
        dec = (review.get(g["qid"], {}).get("decision") or "").strip().lower()
        g["review"] = dec or "pending"
        if dec == "reject":
            continue
        for e in g["relevant"]:
            if normalize(e["evidence"]) not in docs[e["doc_id"]]:
                errors.append(f"{g['qid']}: доказ не знайдено в {e['doc_id']}: {e['evidence'][:70]}")
        g["r2"], g["r3"] = g["qid"] in R2_SET, g["qid"] in R3_SET
        kept.append(g)
    write_jsonl(EVAL / "gold.jsonl", kept)
    n_no = sum(1 for g in kept if not g["answerable"])
    types = {}
    for g in kept:
        types[g["qtype"]] = types.get(g["qtype"], 0) + 1
    print(f"запитів: {len(kept)}, без відповіді: {n_no}, за типом: {types}, "
          f"англійською: {sum(g['lang'] == 'en' for g in kept)}")
    print("статус перевірки:", {s: sum(g['review'] == s for g in kept) for s in {g['review'] for g in kept}})
    if errors:
        print("ПОМИЛКИ:\n  " + "\n  ".join(errors))
        sys.exit(1)


if __name__ == "__main__":
    main()
