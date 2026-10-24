import argparse
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import CLEAN, DOCS, EVAL, RESULTS, read_json, read_jsonl, write_json  # noqa: E402
import chunking  # noqa: E402
from encoders import MODELS, STUB, Encoder  # noqa: E402
from index import build_store, exact_topk  # noqa: E402
from metrics import evaluate_run  # noqa: E402

M, EFC, EFS = 32, 200, 64


def chosen_strategy(cli):
    if cli:
        return cli
    p = RESULTS / "r2_chunking.json"
    return read_json(p)["auto_choice"] if p.exists() else "structural"


def pct(xs, q):
    return float(np.percentile(xs, q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["e5-small", "ml-minilm", "en-minilm"])
    ap.add_argument("--strategy", default=None)
    args = ap.parse_args()
    strat = chosen_strategy(args.strategy)
    docs = read_jsonl(CLEAN / "docs.jsonl")
    gold = [g for g in read_jsonl(EVAL / "gold.jsonl") if g["r3"]]
    rows = []
    for key in args.models:
        enc = Encoder(key)
        units, contexts = chunking.build(strat, docs, encoder=enc if strat == "semantic" else None)
        texts = [u["embed_text"] for u in units]
        truncated = None
        if not STUB:
            tok = enc.model.tokenizer
            truncated = int(sum(len(tok(enc.pp + t)["input_ids"]) > enc.max_seq_length for t in texts))
        t = time.perf_counter()
        vecs = enc.encode_passages(texts, cache=False)
        enc_s = time.perf_counter() - t
        store = build_store(units, vecs, M, EFC, EFS)
        # якість + затримка
        lat, results, qvecs = [], {}, []
        for g in gold:
            times = []
            for rep in range(3):
                t = time.perf_counter()
                q = enc.encode_queries([g["query"]])
                hits = store.search(q, 10)[0]
                times.append((time.perf_counter() - t) * 1000)
            lat.append(st.median(times[1:]))
            qvecs.append(q[0])
            seen, res = set(), []
            for i, _ in hits:
                ctx = units[i].get("parent_id") or units[i]["chunk_id"]
                if ctx not in seen:
                    seen.add(ctx); res.append((contexts[ctx]["text"], units[i]["doc_id"]))
            results[g["qid"]] = res
        mean, per = evaluate_run(results, gold)
        by_lang = {}
        for lang in ["uk", "en"]:
            ids = [g["qid"] for g in gold if g["lang"] == lang and g["qid"] in per]
            by_lang[lang] = {"n": len(ids), "recall@5": round(st.mean(per[q]["recall@5"] for q in ids), 3),
                             "mrr": round(st.mean(per[q]["mrr"] for q in ids), 3)}
        # recall ANN відносно точного пошуку, кілька efSearch
        qv = np.stack(qvecs)
        exact = exact_topk(vecs, qv, 10)
        ann = {}
        for ef in [16, 64, 128]:
            t = time.perf_counter()
            got = store.search(qv, 10, ef_search=ef)
            search_ms = (time.perf_counter() - t) * 1000 / len(qv)
            overlap = [len({i for i, _ in g} & set(e.tolist())) / 10 for g, e in zip(got, exact)]
            ann[ef] = {"ann_recall@10": round(st.mean(overlap), 4), "search_only_ms": round(search_ms, 3)}
        rows.append({"model": key, "hf_name": enc.hf_name, "note": enc.note, "dim": enc.dim,
                     "max_seq_length": getattr(enc, "max_seq_length", None), "truncated_units": truncated,
                     "n_units": len(units), "load_seconds": round(enc.load_seconds, 2),
                     "encode_corpus_seconds": round(enc_s, 2), "hnsw_build_seconds": round(store.build_seconds, 4),
                     "M": M, "efConstruction": EFC, "efSearch": EFS,
                     "recall@5": mean["recall@5"], "mrr": mean["mrr"], "ndcg@10": mean["ndcg@10"], "by_lang": by_lang,
                     "latency_ms_p50": round(st.median(lat), 2), "latency_ms_p95": round(pct(lat, 95), 2),
                     "ann": ann, "per_query": per})
        print(f"{key:10s} recall@5 {mean['recall@5']:.3f} (uk {by_lang['uk']['recall@5']}, en {by_lang['en']['recall@5']})  "
              f"p50 {st.median(lat):.1f} мс  кодування {enc_s:.1f} с  HNSW {store.build_seconds:.3f} с")
    out = {"strategy": strat, "stub": STUB, "queries": [g["qid"] for g in gold], "rows": rows}
    write_json(RESULTS / "r3_embeddings.json", out)

    md = [f"# Порівняння моделей embeddings (стратегія {strat}{', ЗАГЛУШКА' if STUB else ''})", "",
          f"Індекс: FAISS IndexIDMap2(IndexHNSWFlat), METRIC_INNER_PRODUCT на нормалізованих векторах; "
          f"M = {M}, efConstruction = {EFC}, efSearch = {EFS}. Запити: 20 (поле r3), з них "
          f"{sum(g['lang'] == 'en' for g in gold)} англійською.", "",
          "| Модель | Вим. | max_seq | Обрізано фрагм. | Кодування корпусу, с | HNSW, с | recall@5 | recall@5 uk / en | MRR | Затримка p50 / p95, мс |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['model']} ({r['hf_name']}) | {r['dim']} | {r['max_seq_length']} | {r['truncated_units']} | "
                  f"{r['encode_corpus_seconds']} | {r['hnsw_build_seconds']} | {r['recall@5']:.3f} | "
                  f"{r['by_lang']['uk']['recall@5']} / {r['by_lang']['en']['recall@5']} | {r['mrr']:.3f} | "
                  f"{r['latency_ms_p50']} / {r['latency_ms_p95']} |")
    md += ["", "Вплив efSearch (recall HNSW відносно точного перебору в топ-10; час лише пошуку на запит):", "",
           "| Модель | efSearch = 16 | efSearch = 64 | efSearch = 128 |", "|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['model']} | " + " | ".join(f"{r['ann'][ef]['ann_recall@10']} ({r['ann'][ef]['search_only_ms']} мс)"
                                                   for ef in [16, 64, 128]) + " |")
    (DOCS / "embeddings_cmp.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
