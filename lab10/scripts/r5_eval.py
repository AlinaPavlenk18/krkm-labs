"""Результат 5: оцінювання конфігурацій пошуку на всьому золотому наборі.

Конфігурації (за замовчуванням):
  C1 bm25                         — лише BM25;
  C2 dense (найкраща модель Р3)   — лише векторний пошук;
  C3 dense (друга модель)         — для порівняння моделей на повному наборі;
  C4 hybrid                       — BM25 + dense, RRF k = 60;
  C5 hybrid + rerank (mmarco)     — cross-encoder над топ-30;
  C6 hybrid + rerank (bge-m3)     — необов'язково (--with-bge), важчий багатомовний reranker.
Метрики: recall@5, recall@10, MRR, nDCG@10 (середні по запитах з відповіддю), розбивка за типом запиту
і мовою, затримка запиту p50 / p95 (мс, після прогріву), розмір індексу. Для запитів без відповіді —
частка «утримань»: найкращий бал reranker нижче порогу (поріг підбирається на цьому ж наборі — оптимістична оцінка).
Вихід: results/r5_eval.json, docs/search_eval.md
Запуск: python scripts/r5_eval.py [--with-bge]
"""
import argparse
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import CLEAN, DOCS, EVAL, RESULTS, read_json, read_jsonl, write_json  # noqa: E402
import chunking  # noqa: E402
from encoders import MODELS, RERANKERS, STUB, Encoder, Reranker  # noqa: E402
from hybrid import HybridSearcher  # noqa: E402
from metrics import by_type, evaluate_run  # noqa: E402


def hf_cache_size_mb(name):
    try:
        from huggingface_hub import scan_cache_dir
        for repo in scan_cache_dir().repos:
            if repo.repo_id == name:
                return round(repo.size_on_disk / 2**20, 1)
    except Exception:
        return None
    return None


def run_config(label, searcher, mode, gold):
    res, lat, top_scores = {}, [], {}
    for rep in range(2):  # перший прохід — прогрів (кеш, JIT), вимірюємо другий
        for g in gold:
            t = time.perf_counter()
            hits = searcher.search(g["query"], mode=mode, k=10)
            if rep == 1:
                lat.append((time.perf_counter() - t) * 1000)
                res[g["qid"]] = [(searcher.context_text(h), h["doc_id"]) for h in hits]
                top_scores[g["qid"]] = hits[0]["score"] if hits else float("-inf")
    mean, per = evaluate_run(res, gold)
    return {"config": label, "mode": mode, **mean, "latency_ms_p50": round(st.median(lat), 2),
            "latency_ms_p95": round(float(np.percentile(lat, 95)), 2),
            "recall@5_by_type": by_type(per, gold, "recall@5"), "mrr_by_type": by_type(per, gold, "mrr"),
            "recall@5_by_lang": {l: round(st.mean(per[g["qid"]]["recall@5"] for g in gold if g["qid"] in per and g["lang"] == l), 3)
                                 for l in ["uk", "en"]},
            "per_query": per, "top_scores": top_scores}


def abstention(cfg, gold):
    """Поріг за найкращим балом reranker: шукаємо поріг, що максимізує точність рішення «є відповідь / немає»."""
    sc = cfg["top_scores"]
    ans = [sc[g["qid"]] for g in gold if g["answerable"]]
    no = [sc[g["qid"]] for g in gold if not g["answerable"]]
    best = None
    for thr in sorted(set(ans + no)):
        acc = (sum(s >= thr for s in ans) + sum(s < thr for s in no)) / (len(ans) + len(no))
        if best is None or acc > best[0]:
            best = (acc, thr)
    acc, thr = best
    return {"threshold": round(float(thr), 4), "decision_accuracy": round(acc, 3),
            "noanswer_abstained": f"{sum(s < thr for s in no)}/{len(no)}",
            "answerable_wrongly_abstained": f"{sum(s < thr for s in ans)}/{len(ans)}",
            "noanswer_top_scores": [round(float(s), 3) for s in no]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default=None)
    ap.add_argument("--with-bge", action="store_true")
    args = ap.parse_args()
    strat = args.strategy or (read_json(RESULTS / "r2_chunking.json")["auto_choice"] if (RESULTS / "r2_chunking.json").exists() else "structural")
    order = ["e5-small", "ml-minilm"]
    if (RESULTS / "r3_embeddings.json").exists():
        rows = sorted(read_json(RESULTS / "r3_embeddings.json")["rows"], key=lambda r: -r["recall@5"])
        order = [r["model"] for r in rows if r["model"] != "en-minilm"][:2] or order
    docs = read_jsonl(CLEAN / "docs.jsonl")
    gold = read_jsonl(EVAL / "gold.jsonl")
    best, second = order[0], order[1] if len(order) > 1 else None

    enc = Encoder(best)
    units, contexts = chunking.build(strat, docs, encoder=enc if strat == "semantic" else None)
    rr = Reranker("mmarco")
    s = HybridSearcher(units, enc, contexts=contexts, reranker=rr)
    cfgs = [run_config("C1 BM25", s, "bm25", gold),
            run_config(f"C2 dense ({best})", s, "dense", gold)]
    if second:
        enc2 = Encoder(second)
        units2, contexts2 = chunking.build(strat, docs, encoder=enc2 if strat == "semantic" else None)
        s2 = HybridSearcher(units2, enc2, contexts=contexts2)
        cfgs.append(run_config(f"C3 dense ({second})", s2, "dense", gold))
    cfgs.append(run_config(f"C4 hybrid RRF (BM25 + {best})", s, "hybrid", gold))
    c5 = run_config(f"C5 hybrid + rerank ({RERANKERS['mmarco'].split('/')[1]})", s, "hybrid_rerank", gold)
    c5["abstention"] = abstention(c5, gold)
    cfgs.append(c5)
    if args.with_bge:
        s.reranker = Reranker("bge-m3")
        c6 = run_config(f"C6 hybrid + rerank ({RERANKERS['bge-m3'].split('/')[1]})", s, "hybrid_rerank", gold)
        c6["abstention"] = abstention(c6, gold)
        cfgs.append(c6)
    for c in cfgs:
        print(f"{c['config']:45s} R@5 {c['recall@5']:.3f} R@10 {c['recall@10']:.3f} MRR {c['mrr']:.3f} "
              f"nDCG@10 {c['ndcg@10']:.3f}  p50 {c['latency_ms_p50']} мс")
    costs = {"index_vectors_mb": round(s.vectors.nbytes / 2**20, 2), "n_units": len(units), "dim": int(s.vectors.shape[1]),
             "encode_corpus_seconds": round(s.encode_seconds, 2), "bm25_build_seconds": round(s.bm25_build_seconds, 3),
             "model_disk_mb": {MODELS[best][0]: hf_cache_size_mb(MODELS[best][0]),
                               RERANKERS["mmarco"]: hf_cache_size_mb(RERANKERS["mmarco"])}}
    if args.with_bge:
        costs["model_disk_mb"][RERANKERS["bge-m3"]] = hf_cache_size_mb(RERANKERS["bge-m3"])
    n = {"total": len(gold), "answerable": sum(g["answerable"] for g in gold),
         "noanswer": sum(not g["answerable"] for g in gold),
         "by_type": {t: sum(g["qtype"] == t for g in gold) for t in sorted({g["qtype"] for g in gold})},
         "en": sum(g["lang"] == "en" for g in gold)}
    out = {"strategy": strat, "stub": STUB, "models": {"best": best, "second": second}, "gold": n,
           "configs": cfgs, "costs": costs}
    write_json(RESULTS / "r5_eval.json", out)

    md = [f"# Оцінювання пошуку на золотому наборі{' (ЗАГЛУШКА)' if STUB else ''}", "",
          f"Набір: {n['total']} запитів ({n['answerable']} з відповіддю, {n['noanswer']} без відповіді; "
          f"за типом {n['by_type']}; англійською {n['en']}). Стратегія chunking: {strat}.", "",
          "| Конфігурація | recall@5 | recall@10 | MRR | nDCG@10 | p50, мс | p95, мс |", "|---|---|---|---|---|---|---|"]
    for c in cfgs:
        md.append(f"| {c['config']} | {c['recall@5']:.3f} | {c['recall@10']:.3f} | {c['mrr']:.3f} | {c['ndcg@10']:.3f} | "
                  f"{c['latency_ms_p50']} | {c['latency_ms_p95']} |")
    types = sorted({t for c in cfgs for t in c["recall@5_by_type"]})
    md += ["", "recall@5 за типом запиту і мовою:", "", "| Конфігурація | " + " | ".join(types) + " | uk | en |",
           "|---|" + "---|" * (len(types) + 2)]
    for c in cfgs:
        md.append(f"| {c['config']} | " + " | ".join(str(c["recall@5_by_type"].get(t, "—")) for t in types)
                  + f" | {c['recall@5_by_lang']['uk']} | {c['recall@5_by_lang']['en']} |")
    md += ["", "Запити без відповіді (утримання за порогом балу reranker):", ""]
    for c in cfgs:
        if "abstention" in c:
            a = c["abstention"]
            md.append(f"- {c['config']}: поріг {a['threshold']}, утримано {a['noanswer_abstained']} запитів без відповіді, "
                      f"помилково утримано {a['answerable_wrongly_abstained']} запитів з відповіддю, точність рішення {a['decision_accuracy']}.")
    md += ["", f"Вартість: векторів {costs['n_units']} × {costs['dim']} = {costs['index_vectors_mb']} МБ; "
           f"кодування корпусу {costs['encode_corpus_seconds']} с; моделі на диску {costs['model_disk_mb']} (МБ); "
           "зовнішніх API немає (усе локально, 0 грн за запит)."]
    (DOCS / "search_eval.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
