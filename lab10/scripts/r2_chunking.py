"""Результат 2: порівняння стратегій chunking з фіксованою моделлю embeddings.

Для кожної стратегії (fixed, structural, hierarchical, semantic) будується окремий індекс HNSW
з тією самою моделлю (за замовчуванням e5-small) і виконується dense-пошук для 10 тестових запитів
(поле r2 у gold.jsonl). Метрики: recall@5, MRR, середній розмір контексту топ-5 (слів і символів),
кількість фрагментів, час побудови.
Вихід: results/r2_chunking.json, docs/chunking_cmp.md
Запуск: python scripts/r2_chunking.py [--model e5-small]
"""
import argparse
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import CLEAN, DOCS, EVAL, RESULTS, read_jsonl, write_json  # noqa: E402
import chunking  # noqa: E402
from encoders import STUB, Encoder  # noqa: E402
from hybrid import HybridSearcher  # noqa: E402
from metrics import evaluate_run  # noqa: E402

PARAMS = {"fixed": {"size": 120, "overlap": 30}, "structural": {"max_words": 180, "min_words": 25},
          "hierarchical": {"child_words": 60, "parent_max_words": 400},
          "semantic": {"percentile": 20, "min_words": 40, "max_words": 200}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="e5-small")
    args = ap.parse_args()
    docs = read_jsonl(CLEAN / "docs.jsonl")
    gold = [g for g in read_jsonl(EVAL / "gold.jsonl") if g["r2"]]
    enc = Encoder(args.model)
    rows = []
    for strat in chunking.STRATEGIES:
        t = time.perf_counter()
        units, contexts = chunking.build(strat, docs, encoder=enc, **PARAMS[strat])
        chunk_s = time.perf_counter() - t
        s = HybridSearcher(units, enc, contexts=contexts)
        results, ctx_words, ctx_chars = {}, [], []
        for g in gold:
            hits = s.search(g["query"], mode="dense", k=10)
            results[g["qid"]] = [(s.context_text(h), h["doc_id"]) for h in hits]
            top5 = [s.context_text(h) for h in hits[:5]]
            ctx_words.append(sum(len(x.split()) for x in top5))
            ctx_chars.append(sum(len(x) for x in top5))
        mean, per = evaluate_run(results, gold)
        sizes = [len(c["text"].split()) for c in contexts.values()]
        rows.append({"strategy": strat, "params": PARAMS[strat], "n_index_units": len(units),
                     "n_context_units": len(contexts), "unit_words_mean": round(st.mean(len(u["text"].split()) for u in units), 1),
                     "context_unit_words_mean": round(st.mean(sizes), 1),
                     "recall@5": mean["recall@5"], "mrr": mean["mrr"], "ndcg@10": mean["ndcg@10"],
                     "context_top5_words_mean": round(st.mean(ctx_words), 1),
                     "context_top5_chars_mean": round(st.mean(ctx_chars), 1),
                     "chunking_seconds": round(chunk_s, 2), "encode_seconds": round(s.encode_seconds, 2),
                     "per_query_recall@5": {q: v["recall@5"] for q, v in per.items()}})
        print(f"{strat:13s} фрагментів {len(units):4d}  recall@5 {mean['recall@5']:.3f}  MRR {mean['mrr']:.3f}  "
              f"контекст топ-5 {st.mean(ctx_words):.0f} слів")
    best = max(rows, key=lambda r: (round(r["recall@5"], 3), -r["context_top5_words_mean"]))
    out = {"model": args.model, "stub": STUB, "queries": [g["qid"] for g in gold], "rows": rows,
           "auto_choice": best["strategy"]}
    write_json(RESULTS / "r2_chunking.json", out)

    md = [f"# Порівняння стратегій chunking (модель {args.model}{', ЗАГЛУШКА' if STUB else ''})", "",
          f"Запити: {', '.join(out['queries'])} (10 запитів з eval/gold.jsonl, поле r2). Пошук — dense, HNSW (M = 32, efSearch = 64).", "",
          "| Стратегія | Параметри | Фрагментів | Сер. розмір фрагмента, слів | recall@5 | MRR | Контекст топ-5, слів | Контекст топ-5, символів |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        md.append(f"| {r['strategy']} | {p} | {r['n_index_units']} | {r['unit_words_mean']} | {r['recall@5']:.3f} | "
                  f"{r['mrr']:.3f} | {r['context_top5_words_mean']} | {r['context_top5_chars_mean']} |")
    md += ["", f"Автоматичний вибір (найвищий recall@5, за рівності — менший контекст): **{best['strategy']}**.",
           "", "Обґрунтування вибору — у звіті (Результат 2)."]
    (DOCS / "chunking_cmp.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
