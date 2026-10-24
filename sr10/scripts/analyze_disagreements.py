"""Крок 4. Запити, де моделі розходяться найбільше, — матеріал для аналізу причин.
Вихід: docs/disagreements.md
Запуск: python scripts/analyze_disagreements.py [--top 8]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import DATA, DOCS, EVAL, RESULTS, read_json, read_jsonl  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    R = read_json(RESULTS / "sr10_results.json")
    corpus = {c["chunk_id"]: c for c in read_jsonl(DATA / "corpus.jsonl")}
    queries = {q["qid"]: q for q in read_jsonl(EVAL / "queries.jsonl")}
    models = [m for m in R["models"] if m != "en-minilm"]
    rows = []
    for qid, q in queries.items():
        recs = [R["models"][m]["per_query_uk"][qid]["recall@5"] for m in models]
        ranks = [R["models"][m]["per_query_uk"][qid]["first_rel_rank"] or 11 for m in models]
        rows.append((max(recs) - min(recs) + (max(ranks) - min(ranks)) / 10, qid))
    rows.sort(reverse=True)
    L = ["# Найбільші розбіжності моделей (uk-запити)", "", "✓ — фрагмент золотий; бал — косинусна схожість (для BM25 — бал BM25).", ""]
    for score, qid in rows[: a.top]:
        q = queries[qid]
        L += [f"## {qid} ({q['qtype']}): «{q['uk']}»", "", f"Золоті фрагменти: {', '.join(q['gold_chunks'])}. Міра розбіжності: {score:.2f}.", "",
              "| Модель | recall@5 | ранг 1-го релевантного | Топ-5 |", "|---|---|---|---|"]
        for m in list(R["models"]) + ["bm25"]:
            per = R["baseline_bm25"]["per_query_uk"][qid] if m == "bm25" else R["models"][m]["per_query_uk"][qid]
            top = "<br>".join(f"{'✓' if c in q['gold_chunks'] else '·'} {c} ({s}) {corpus[c]['text'][:140].replace('|', '/')}…" for c, s in per["top10"][:5])
            L.append(f"| {m} | {per['recall@5']:.2f} | {per['first_rel_rank']} | {top} |")
        L.append("")
    (DOCS / "disagreements.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("найбільш спірні запити:", [qid for _, qid in rows[: a.top]])


if __name__ == "__main__":
    main()
