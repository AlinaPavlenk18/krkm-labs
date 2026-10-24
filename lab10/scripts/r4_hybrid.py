"""Результат 4: BM25 + dense + RRF (k = 60), reranker cross-encoder (топ-30 -> топ-5), pre-filter.

1) Усі запити з відповіддю з gold.jsonl у 4 режимах: bm25, dense, hybrid, hybrid_rerank.
2) Як reranker змінює топ-5: для скількох запитів змінився склад/порядок, приклад.
3) Pre-filter за метаданими (sensitivity, type, date) проти post-filter: перевірка, що всі результати
   задовольняють фільтр і що pre-filter не «з'їдає» топ-5.
4) Автоматичний добір прикладів: 3 запити, де hybrid виграє, і 1, де програє (за рангом першого
   релевантного фрагмента порівняно з BM25 і dense).
Вихід: results/r4_hybrid.json, docs/hybrid_report.md
Запуск: python scripts/r4_hybrid.py [--model e5-small] [--reranker mmarco] [--strategy structural]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import CLEAN, DOCS, EVAL, RESULTS, read_json, read_jsonl, write_json  # noqa: E402
import chunking  # noqa: E402
from encoders import STUB, Encoder, Reranker  # noqa: E402
from hybrid import Filters, HybridSearcher, RRF_K, CANDIDATES  # noqa: E402
from metrics import evaluate_run, judge  # noqa: E402

MODES = ["bm25", "dense", "hybrid", "hybrid_rerank"]

FILTER_TESTS = [
    ("q35", "роль «зовнішній користувач»: лише public", Filters(max_sensitivity="public")),
    ("q39", "роль «аналітик»: public + internal (без restricted)", Filters(max_sensitivity="internal")),
    ("q14", "лише нормативні документи (regulation, procedure, policy)", Filters(types={"regulation", "procedure", "policy"})),
    ("q19", "лише документи від 2026-10-15", Filters(date_from="2026-10-15")),
]


def first_rel(hits, s, g):
    cov = judge([s.context_text(h) for h in hits], [h["doc_id"] for h in hits], g["relevant"])
    return next((r for r, c in enumerate(cov, 1) if c), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--reranker", default="mmarco")
    ap.add_argument("--strategy", default=None)
    args = ap.parse_args()
    strat = args.strategy or (read_json(RESULTS / "r2_chunking.json")["auto_choice"] if (RESULTS / "r2_chunking.json").exists() else "structural")
    model = args.model
    if not model:
        p = RESULTS / "r3_embeddings.json"
        model = max(read_json(p)["rows"], key=lambda r: r["recall@5"])["model"] if p.exists() else "e5-small"
    docs = read_jsonl(CLEAN / "docs.jsonl")
    gold = read_jsonl(EVAL / "gold.jsonl")
    ans = [g for g in gold if g["answerable"]]
    enc = Encoder(model)
    units, contexts = chunking.build(strat, docs, encoder=enc if strat == "semantic" else None)
    s = HybridSearcher(units, enc, contexts=contexts, reranker=Reranker(args.reranker))

    # 1) чотири режими
    runs, ranks, top5 = {}, {}, {}
    for m in MODES:
        res = {}
        for g in ans:
            hits = s.search(g["query"], mode=m, k=10)
            res[g["qid"]] = [(s.context_text(h), h["doc_id"]) for h in hits]
            ranks.setdefault(g["qid"], {})[m] = first_rel(hits, s, g)
            top5.setdefault(g["qid"], {})[m] = [h["context_id"] for h in hits[:5]]
        runs[m] = evaluate_run(res, gold)[0]
        print(f"{m:14s} recall@5 {runs[m]['recall@5']:.3f}  MRR {runs[m]['mrr']:.3f}  nDCG@10 {runs[m]['ndcg@10']:.3f}")

    # 2) вплив reranker на топ-5
    changed_set = [q for q in top5 if set(top5[q]["hybrid"]) != set(top5[q]["hybrid_rerank"])]
    changed_order = [q for q in top5 if top5[q]["hybrid"] != top5[q]["hybrid_rerank"]]
    ex_q = max(changed_order, key=lambda q: (ranks[q]["hybrid"] or 99) - (ranks[q]["hybrid_rerank"] or 99), default=None)
    rerank_example = None
    if ex_q:
        g = next(x for x in ans if x["qid"] == ex_q)
        rerank_example = {"qid": ex_q, "query": g["query"], "hybrid_top5": top5[ex_q]["hybrid"],
                          "rerank_top5": top5[ex_q]["hybrid_rerank"],
                          "first_rel_hybrid": ranks[ex_q]["hybrid"], "first_rel_rerank": ranks[ex_q]["hybrid_rerank"]}

    # 3) pre-filter vs post-filter
    ftests = []
    for qid, label, f in FILTER_TESTS:
        g = next(x for x in gold if x["qid"] == qid)
        no = s.search(g["query"], mode="hybrid_rerank", k=5)
        pre = s.search(g["query"], mode="hybrid_rerank", k=5, filters=f)
        post = s.search(g["query"], mode="hybrid_rerank", k=5, filters=f, post_filter=True)
        desc = lambda hits: [{"id": h["context_id"], "type": units[h["idx"]]["type"], "sens": units[h["idx"]]["sensitivity"],
                              "date": units[h["idx"]]["date"]} for h in hits]
        ftests.append({"qid": qid, "query": g["query"], "filter": label, "repr": repr(f),
                       "no_filter": desc(no), "pre_filter": desc(pre), "post_filter": desc(post),
                       "violations_pre": sum(not f.ok(units[h["idx"]]) for h in pre),
                       "violations_no_filter": sum(not f.ok(units[h["idx"]]) for h in no),
                       "n_pre": len(pre), "n_post": len(post),
                       "first_rel_pre": first_rel(pre, s, g)})
        print(f"фільтр {qid}: без фільтра порушень {ftests[-1]['violations_no_filter']}, pre: {len(pre)} рез., "
              f"порушень {ftests[-1]['violations_pre']}; post: {len(post)} рез.")

    # 4) приклади виграшу / програшу hybrid
    def r(x):
        return x if x is not None else 99
    wins, losses = [], []
    for g in ans:
        q = ranks[g["qid"]]
        best_single = min(r(q["bm25"]), r(q["dense"]))
        worst_single = max(r(q["bm25"]), r(q["dense"]))
        if r(q["hybrid"]) < best_single or (r(q["hybrid"]) < 99 and r(q["hybrid"]) <= best_single < worst_single == 99 and best_single > 1):
            wins.append((best_single - r(q["hybrid"]) + (worst_single - r(q["hybrid"])) / 100, g["qid"]))
        if r(q["hybrid"]) > best_single:
            losses.append((r(q["hybrid"]) - best_single, g["qid"]))
    wins = [q for _, q in sorted(wins, reverse=True)]
    losses = [q for _, q in sorted(losses, reverse=True)]
    show = lambda q: {"qid": q, "query": next(x["query"] for x in ans if x["qid"] == q), "qtype": next(x["qtype"] for x in ans if x["qid"] == q),
                      "lang": next(x["lang"] for x in ans if x["qid"] == q), **{m: ranks[q][m] for m in MODES}}
    out = {"model": model, "reranker": args.reranker, "strategy": strat, "stub": STUB, "rrf_k": RRF_K, "candidates": CANDIDATES,
           "runs": runs, "ranks": ranks,
           "rerank_changed_top5_set": len(changed_set), "rerank_changed_top5_order": len(changed_order), "n_answerable": len(ans),
           "rerank_example": rerank_example, "filter_tests": ftests,
           "wins": [show(q) for q in wins[:6]], "losses": [show(q) for q in losses[:3]],
           "n_wins": len(wins), "n_losses": len(losses)}
    write_json(RESULTS / f"r4_hybrid{'' if args.reranker == 'mmarco' else '_' + args.reranker}.json", out)

    md = [f"# Гібридний пошук і reranking (модель {model}, reranker {args.reranker}, стратегія {strat}{', ЗАГЛУШКА' if STUB else ''})", "",
          f"RRF: k = {RRF_K}, кандидатів з кожного списку {CANDIDATES}; reranker переранжовує топ-{CANDIDATES} після RRF.", "",
          "| Режим | recall@5 | recall@10 | MRR | nDCG@10 |", "|---|---|---|---|---|"]
    for m in MODES:
        md.append(f"| {m} | {runs[m]['recall@5']:.3f} | {runs[m]['recall@10']:.3f} | {runs[m]['mrr']:.3f} | {runs[m]['ndcg@10']:.3f} |")
    md += ["", f"Reranker змінив склад топ-5 у {len(changed_set)} з {len(ans)} запитів, порядок — у {len(changed_order)}.", ""]
    if rerank_example:
        md += [f"Приклад ({rerank_example['qid']}: «{rerank_example['query']}»): hybrid топ-5 = {rerank_example['hybrid_top5']}; "
               f"після reranker = {rerank_example['rerank_top5']}; ранг першого релевантного {rerank_example['first_rel_hybrid']} → "
               f"{rerank_example['first_rel_rerank']}.", ""]
    md += ["## Pre-filter за метаданими", "", "| Запит | Фільтр | Порушень без фільтра | pre-filter: результатів / порушень | post-filter: результатів |",
           "|---|---|---|---|---|"]
    for t in ftests:
        md.append(f"| {t['qid']} | {t['filter']} | {t['violations_no_filter']} | {t['n_pre']} / {t['violations_pre']} | {t['n_post']} |")
    md += ["", "## Ранг першого релевантного фрагмента: виграші та програші hybrid", "",
           "| Запит | Тип | bm25 | dense | hybrid | hybrid_rerank |", "|---|---|---|---|---|---|"]
    for w in out["wins"][:3] + out["losses"][:1]:
        md.append(f"| {w['qid']} «{w['query']}» | {w['qtype']}/{w['lang']} | {w['bm25']} | {w['dense']} | {w['hybrid']} | {w['hybrid_rerank']} |")
    md += ["", f"Перші три рядки — виграші (з {len(wins)}), останній — програш (з {len(losses)}). None = немає в топ-10."]
    (DOCS / f"hybrid_report{'' if args.reranker == 'mmarco' else '_' + args.reranker}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
