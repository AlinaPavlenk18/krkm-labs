"""Крок 1. 30 запитів із золотою розміткою (з ЛР10) + варіанти для перевірки мови й стійкості.

Вхід:  eval/lab10_gold.jsonl (золотий набір ЛР10, усі 50 запитів прийнято вручну),
       data/corpus.jsonl (341 структурний фрагмент ЛР10),
       eval/variants_llm.jsonl (англійський переклад і українське перефразування кожного запиту — чернетка LLM).
Вихід: eval/queries.jsonl — 30 запитів: qid, qtype, uk, en, uk_para, докази (evidence) і золоті фрагменти
       (gold_chunks: chunk_id фрагментів corpus.jsonl, що містять доказ);
       eval/variants_review.csv — аркуш перевірки варіантів людиною (decision: accept / edit / reject);
       docs/queries.md — таблиця запитів і золотих фрагментів для звіту.
Якщо варіант відхилено (reject), він не бере участі в експерименті для цієї мови.
Запуск: python scripts/build_queries.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import DATA, DOCS, EVAL, read_jsonl, write_jsonl
from metrics import covers  

SELECTED = { 
    "keyword": ["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09", "q10", "q11"],
    "paraphrase": ["q14", "q15", "q16", "q17", "q18", "q19", "q20", "q21", "q22", "q23", "q24"],
    "multihop": ["q33", "q34", "q35", "q36", "q37", "q38", "q42", "q43"],
}


def read_review(p):
    if not p.exists():
        return {}
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    first = text.splitlines()[0] if text else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    out = {}
    for r in csv.DictReader(text.splitlines(), delimiter=delim):
        r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
        out[(r["qid"], r["variant"])] = r
    return out


def main():
    gold = {g["qid"]: g for g in read_jsonl(EVAL / "lab10_gold.jsonl")}
    corpus = read_jsonl(DATA / "corpus.jsonl")
    var = {v["qid"]: v for v in read_jsonl(EVAL / "variants_llm.jsonl")}
    review_path = EVAL / "variants_review.csv"
    review = read_review(review_path)
    rows, sheet = [], []
    for qtype, ids in SELECTED.items():
        for qid in ids:
            g = gold[qid]
            assert g["answerable"] and g["lang"] == "uk", qid
            gold_chunks = sorted({c["chunk_id"] for c in corpus for e in g["relevant"] if covers(c["text"], c["doc_id"], e)})
            assert gold_chunks, f"{qid}: жоден фрагмент не містить доказу"
            q = {"qid": qid, "qtype": qtype, "uk": g["query"], "en": var[qid]["en"], "uk_para": var[qid]["uk_para"],
                 "relevant": g["relevant"], "gold_chunks": gold_chunks}
            for v in ["en", "uk_para"]:
                r = review.get((qid, v))
                if r and r.get("decision", "").lower() == "edit" and r.get("fixed_text"):
                    q[v] = r["fixed_text"]
                q[f"{v}_review"] = (r or {}).get("decision", "").lower() or "pending"
                sheet.append([qid, qtype, v, g["query"], var[qid][v], "", ""])
            rows.append(q)
    write_jsonl(EVAL / "queries.jsonl", rows)
    if not review_path.exists():
        with open(review_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["qid", "qtype", "variant", "original_uk", "variant_text", "decision", "fixed_text"])
            w.writerows(sheet)
    md = ["# 30 запитів СР10 і золоті фрагменти", "",
          "| qid | Тип | Запит (uk) | Золоті фрагменти (corpus.jsonl) |", "|---|---|---|---|"]
    for q in rows:
        md.append(f"| {q['qid']} | {q['qtype']} | {q['uk']} | {', '.join(q['gold_chunks'])} |")
    (DOCS / "queries.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    n_gold = sum(len(q["gold_chunks"]) for q in rows)
    st = {}
    for q in rows:
        for v in ["en", "uk_para"]:
            st[q[f"{v}_review"]] = st.get(q[f"{v}_review"], 0) + 1
    print(f"запитів: {len(rows)} ({ {k: len(v) for k, v in SELECTED.items()} }); золотих фрагментів: {n_gold} "
          f"(у середньому {n_gold / len(rows):.1f} на запит); варіанти — статус перевірки: {st}")


if __name__ == "__main__":
    main()
