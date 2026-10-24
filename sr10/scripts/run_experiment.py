"""Кроки 2–3. Індекси для кількох моделей embeddings, recall@5 / MRR, затримка, розмір індексу.

Для кожної моделі:
  1) завантаження (час, кількість параметрів, розмір на диску, max_seq_length, розмірність);
  2) кодування 341 фрагмента corpus.jsonl («назва. секція. текст»): час, фрагментів/с, скільки обрізано за max_seq_length;
  3) індекс FAISS IndexFlatIP (точний пошук: порівнюємо моделі, а не наближення ANN) на нормалізованих векторах;
     розмір індексу Flat і, для довідки, HNSW (M = 32);
  4) 30 запитів у трьох варіантах: uk (оригінал), en (переклад), uk_para (перефразування) — recall@5, recall@10, MRR, hit@5;
  5) затримка запиту (кодування + пошук) на uk-запитах: 1 прогрів + 3 повтори, медіана; p50 / p95 по запитах;
  6) абляції: без нормалізації (скалярний добуток «сирих» векторів) і для e5 — без префіксів «query: » / «passage: ».
Базова лінія без нейромереж: BM25 (rank_bm25, стемінг як у ЛР10).

Вихід: results/sr10_results.json (усі числа + топ-10 для кожного запиту), docs/sr10_tables.md.
Запуск: python scripts/run_experiment.py [--models e5-small e5-base bge-m3 ml-minilm en-minilm] [--threads 4]
Заглушка без моделей (лише перевірка коду): $env:SR10_STUB="1"
"""
import argparse
import os
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import DATA, DOCS, EVAL, RESULTS, read_jsonl, tokenize, write_json 
from metrics import evaluate_run, judge  

STUB = os.environ.get("SR10_STUB") == "1"
MODELS = {
    # ключ: (Hugging Face, префікс запиту, префікс фрагмента, коротка характеристика)
    "e5-small": ("intfloat/multilingual-e5-small", "query: ", "passage: ", "багатомовна, мала"),
    "e5-base": ("intfloat/multilingual-e5-base", "query: ", "passage: ", "багатомовна, базова"),
    "bge-m3": ("BAAI/bge-m3", "", "", "багатомовна, велика, довгий контекст"),
    "ml-minilm": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "", "", "багатомовна, перефразування"),
    "en-minilm": ("sentence-transformers/all-MiniLM-L6-v2", "", "", "англомовна (контроль мови)"),
}
VARIANTS = ["uk", "en", "uk_para"]


class Model:
    def __init__(self, key):
        self.key = key
        self.hf, self.qp, self.pp, self.note = MODELS[key]
        t = time.perf_counter()
        if STUB:
            from sklearn.decomposition import TruncatedSVD
            from sklearn.feature_extraction.text import TfidfVectorizer
            texts = [c["text"] for c in read_jsonl(DATA / "corpus.jsonl")]
            ng = {"e5-small": (3, 5), "e5-base": (2, 5), "bge-m3": (3, 6), "ml-minilm": (2, 4), "en-minilm": (1, 2)}[key]
            self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=ng, min_df=2, sublinear_tf=True).fit(texts)
            self.svd = TruncatedSVD(64, random_state=42).fit(self.vec.transform(texts))
            self.dim, self.max_len, self.params = 64, 512, 0
        else:
            from sentence_transformers import SentenceTransformer
            self.m = SentenceTransformer(self.hf, device="cpu")
            get_dim = getattr(self.m, "get_embedding_dimension", None) or getattr(self.m, "get_sentence_embedding_dimension")
            self.dim, self.max_len = get_dim(), self.m.max_seq_length
            self.params = int(sum(p.numel() for p in self.m.parameters()))
        self.load_s = time.perf_counter() - t

    def encode(self, texts, prefix, normalize=True, batch_size=16):
        if STUB:
            x = self.svd.transform(self.vec.transform(texts)).astype("float32") * 3.0
        else:
            x = self.m.encode([prefix + t for t in texts], batch_size=batch_size, normalize_embeddings=False,
                              convert_to_numpy=True, show_progress_bar=False).astype("float32")
        if normalize:
            x = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)
        return x

    def n_truncated(self, texts):
        if STUB:
            return 0
        tok = self.m.tokenizer
        return int(sum(len(tok(self.pp + t, add_special_tokens=True)["input_ids"]) > self.max_len for t in texts))


def disk_mb(hf):
    try:
        from huggingface_hub import scan_cache_dir
        for r in scan_cache_dir().repos:
            if r.repo_id == hf:
                return round(r.size_on_disk / 2**20, 1)
    except Exception:
        pass
    return None

def flat_index(vecs):
    import faiss
    idx = faiss.IndexFlatIP(vecs.shape[1])
    idx.add(vecs)
    return idx


def index_sizes(vecs):
    import faiss
    flat = flat_index(vecs)
    h = faiss.IndexHNSWFlat(vecs.shape[1], 32, faiss.METRIC_INNER_PRODUCT)
    h.add(vecs)
    return round(faiss.serialize_index(flat).nbytes / 2**20, 3), round(faiss.serialize_index(h).nbytes / 2**20, 3)


def run_queries(search_fn, queries, variant, corpus):
    """search_fn(text) -> [(idx, score)] топ-10. Повертає (метрики, по-запитні результати)."""
    res, hits = {}, {}
    for q in queries:
        if q.get(f"{variant}_review") == "reject":
            continue
        top = search_fn(q[variant])
        res[q["qid"]] = [(corpus[i]["text"], corpus[i]["doc_id"]) for i, _ in top]
        hits[q["qid"]] = [(corpus[i]["chunk_id"], round(float(s), 4)) for i, s in top]
    gold = [{"qid": q["qid"], "answerable": True, "relevant": q["relevant"], "qtype": q["qtype"]} for q in queries if q["qid"] in res]
    mean, per = evaluate_run(res, gold)
    for q in queries:
        if q["qid"] in per:
            per[q["qid"]]["hit@5"] = float(any(c in q["gold_chunks"] for c, _ in hits[q["qid"]][:5]))
            per[q["qid"]]["top10"] = hits[q["qid"]]
    mean["hit@5"] = round(st.mean(p["hit@5"] for p in per.values()), 4)
    return mean, per


def by_group(per, queries, key):
    out = {}
    for q in queries:
        if q["qid"] in per:
            out.setdefault(q[key], []).append(per[q["qid"]]["recall@5"])
    return {k: round(st.mean(v), 3) for k, v in sorted(out.items())}


def domain_of(q):
    """Домен запиту = група документів (kb / gen / prj), до якої належить більшість його золотих фрагментів.
    Нічия вирішується детерміновано за алфавітним порядком групи (gen < kb < prj)."""
    from collections import Counter
    groups = Counter("".join(ch for ch in c.split("#")[0] if ch.isalpha()) for c in q["gold_chunks"])
    g = sorted(groups.items(), key=lambda x: (-x[1], x[0]))[0][0]
    return {"kb": "статті бази знань", "gen": "реєстри (числа, ідентифікатори)", "prj": "проєктні документи (код, таблиці)"}[g]


def recompute_tables():
    from common import read_json
    out = read_json(RESULTS / "sr10_results.json")
    queries = read_jsonl(EVAL / "queries.jsonl")
    for q in queries:
        q["domain"] = domain_of(q)
    out["query_domains"] = {q["qid"]: q["domain"] for q in queries}
    out["domain_counts"] = {d: sum(q["domain"] == d for q in queries) for d in sorted({q["domain"] for q in queries})}
    for r in [out["baseline_bm25"]] + list(out["models"].values()):
        r["by_domain_uk"] = by_group(r["per_query_uk"], queries, "domain")
    write_json(RESULTS / "sr10_results.json", out)
    write_tables(out)
    print("домени:", out["domain_counts"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=list(MODELS))
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--tables-only", action="store_true", help="лише перерахувати домени й таблиці з results/sr10_results.json")
    a = ap.parse_args()
    if a.tables_only:
        return recompute_tables()
    if not STUB:
        import torch
        torch.set_num_threads(a.threads)   
    corpus = read_jsonl(DATA / "corpus.jsonl")
    queries = read_jsonl(EVAL / "queries.jsonl")
    for q in queries:
        q["domain"] = domain_of(q)
    texts = [f"{c['title']}. {c['section']}. {c['text']}" if c["section"] != c["title"] else f"{c['title']}. {c['text']}" for c in corpus]
    out = {"stub": STUB, "threads": a.threads, "n_fragments": len(corpus), "n_queries": len(queries),
           "query_domains": {q["qid"]: q["domain"] for q in queries}, "models": {}, "baseline_bm25": {}}
    out["domain_counts"] = {d: sum(q["domain"] == d for q in queries) for d in sorted({q["domain"] for q in queries})}
    out["type_counts"] = {t: sum(q["qtype"] == t for q in queries) for t in sorted({q["qtype"] for q in queries})}

    # ---- BM25
    from rank_bm25 import BM25Okapi
    t = time.perf_counter()
    bm = BM25Okapi([tokenize(x) for x in texts])
    bm_build = time.perf_counter() - t

    def bm_search(qtext):
        s = bm.get_scores(tokenize(qtext))
        o = np.argsort(-s)[:10]
        return [(int(i), float(s[i])) for i in o]
    lat = []
    for q in queries:
        t = time.perf_counter(); bm_search(q["uk"]); lat.append((time.perf_counter() - t) * 1000)
    b = {"build_s": round(bm_build, 3), "latency_ms_p50": round(st.median(lat), 2), "latency_ms_p95": round(float(np.percentile(lat, 95)), 2)}
    for v in VARIANTS:
        m, per = run_queries(bm_search, queries, v, corpus)
        b[v] = m
        if v == "uk":
            b["per_query_uk"] = per
            b["by_type_uk"] = by_group(per, queries, "qtype")
            b["by_domain_uk"] = by_group(per, queries, "domain")
    out["baseline_bm25"] = b
    print(f"{'BM25':10s} uk R@5 {b['uk']['recall@5']:.3f}  en {b['en']['recall@5']:.3f}  para {b['uk_para']['recall@5']:.3f}  p50 {b['latency_ms_p50']} мс")

    # ---- моделі
    for key in a.models:
        mdl = Model(key)
        r = {"hf": mdl.hf, "note": mdl.note, "dim": mdl.dim, "max_seq_length": mdl.max_len, "params_m": round(mdl.params / 1e6, 1),
             "disk_mb": None if STUB else disk_mb(mdl.hf), "load_s": round(mdl.load_s, 2), "truncated": mdl.n_truncated(texts)}
        t = time.perf_counter()
        raw = mdl.encode(texts, mdl.pp, normalize=False)
        r["encode_corpus_s"] = round(time.perf_counter() - t, 2)
        r["fragments_per_s"] = round(len(texts) / max(r["encode_corpus_s"], 1e-6), 1)
        vecs = raw / (np.linalg.norm(raw, axis=1, keepdims=True) + 1e-12)
        r["raw_norm_mean"], r["raw_norm_std"] = round(float(np.linalg.norm(raw, axis=1).mean()), 3), round(float(np.linalg.norm(raw, axis=1).std()), 3)
        r["index_flat_mb"], r["index_hnsw_mb"] = index_sizes(vecs)
        idx = flat_index(vecs)

        def search(qtext, _m=mdl, _idx=idx, prefix=None, norm=True):
            qv = _m.encode([qtext], _m.qp if prefix is None else prefix, normalize=norm)
            D, I = _idx.search(qv, 10)
            return list(zip(I[0].tolist(), D[0].tolist()))
        # затримка
        search(queries[0]["uk"])
        lat = []
        for q in queries:
            ts = []
            for _ in range(3):
                t = time.perf_counter(); search(q["uk"]); ts.append((time.perf_counter() - t) * 1000)
            lat.append(st.median(ts))
        r["latency_ms_p50"], r["latency_ms_p95"] = round(st.median(lat), 2), round(float(np.percentile(lat, 95)), 2)
        for v in VARIANTS:
            m, per = run_queries(search, queries, v, corpus)
            r[v] = m
            r[f"per_query_{v}"] = per
        r["by_type_uk"] = by_group(r["per_query_uk"], queries, "qtype")
        r["by_domain_uk"] = by_group(r["per_query_uk"], queries, "domain")
        # абляція 1: без нормалізації
        idx_raw = flat_index(raw)
        m, _ = run_queries(lambda x: search(x, _idx=idx_raw, norm=False), queries, "uk", corpus)
        r["ablation_no_norm_uk"] = m
        # абляція 2: e5 без префіксів
        if mdl.qp or mdl.pp:
            raw_np = mdl.encode(texts, "", normalize=True)
            idx_np = flat_index(raw_np)
            m, _ = run_queries(lambda x: search(x, _idx=idx_np, prefix=""), queries, "uk", corpus)
            r["ablation_no_prefix_uk"] = m
        out["models"][key] = r
        print(f"{key:10s} uk R@5 {r['uk']['recall@5']:.3f} MRR {r['uk']['mrr']:.3f}  en {r['en']['recall@5']:.3f}  para {r['uk_para']['recall@5']:.3f}  "
              f"p50 {r['latency_ms_p50']} мс  корпус {r['encode_corpus_s']} с  без норм. {r['ablation_no_norm_uk']['recall@5']:.3f}"
              + (f"  без префіксів {r['ablation_no_prefix_uk']['recall@5']:.3f}" if "ablation_no_prefix_uk" in r else ""))
        del mdl
    write_json(RESULTS / "sr10_results.json", out)
    write_tables(out)


def write_tables(out):
    M = out["models"]
    L = [f"# Результати СР10{' (ЗАГЛУШКА — числа не для звіту)' if out['stub'] else ''}", "",
         f"Корпус: {out['n_fragments']} фрагментів; запитів: {out['n_queries']}; потоків CPU: {out['threads']}; індекс — FAISS IndexFlatIP (точний пошук).", "",
         "## Якість (uk-запити) і вартість", "",
         "| Модель | Парам., млн | Вим. | max_seq | Обрізано | Диск, МБ | Кодування корпусу, с | Індекс Flat / HNSW, МБ | recall@5 | recall@10 | MRR | hit@5 | p50 / p95, мс |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    b = out["baseline_bm25"]
    L.append(f"| BM25 (базова) | — | — | — | — | — | {b['build_s']} | — | {b['uk']['recall@5']:.3f} | {b['uk']['recall@10']:.3f} | {b['uk']['mrr']:.3f} | {b['uk']['hit@5']:.3f} | {b['latency_ms_p50']} / {b['latency_ms_p95']} |")
    for k, r in M.items():
        L.append(f"| {k} ({r['hf']}) | {r['params_m']} | {r['dim']} | {r['max_seq_length']} | {r['truncated']} | {r['disk_mb']} | {r['encode_corpus_s']} | "
                 f"{r['index_flat_mb']} / {r['index_hnsw_mb']} | {r['uk']['recall@5']:.3f} | {r['uk']['recall@10']:.3f} | {r['uk']['mrr']:.3f} | {r['uk']['hit@5']:.3f} | "
                 f"{r['latency_ms_p50']} / {r['latency_ms_p95']} |")
    L += ["", "## Мова і стійкість (recall@5 / MRR)", "", "| Модель | uk | en (переклад) | uk_para (перефразування) |", "|---|---|---|---|"]
    L.append(f"| BM25 | {b['uk']['recall@5']:.3f} / {b['uk']['mrr']:.3f} | {b['en']['recall@5']:.3f} / {b['en']['mrr']:.3f} | {b['uk_para']['recall@5']:.3f} / {b['uk_para']['mrr']:.3f} |")
    for k, r in M.items():
        L.append(f"| {k} | {r['uk']['recall@5']:.3f} / {r['uk']['mrr']:.3f} | {r['en']['recall@5']:.3f} / {r['en']['mrr']:.3f} | {r['uk_para']['recall@5']:.3f} / {r['uk_para']['mrr']:.3f} |")
    types = sorted({t for r in [b] + list(M.values()) for t in r["by_type_uk"]})
    doms = sorted({t for r in [b] + list(M.values()) for t in r["by_domain_uk"]})
    L += ["", "## recall@5 за типом запиту і доменом (uk)", "", "| Модель | " + " | ".join([f"{t} ({out['type_counts'][t]})" for t in types] + [f"{d} ({out['domain_counts'][d]})" for d in doms]) + " |", "|---|" + "---|" * (len(types) + len(doms))]
    for name, r in [("BM25", b)] + list(M.items()):
        L.append(f"| {name} | " + " | ".join(str(r["by_type_uk"].get(t, "—")) for t in types) + " | " + " | ".join(str(r["by_domain_uk"].get(d, "—")) for d in doms) + " |")
    L += ["", "## Абляції (uk, recall@5)", "", "| Модель | звичайно | без нормалізації | без префіксів e5 | норма «сирих» векторів (середнє ± σ) |", "|---|---|---|---|---|"]
    for k, r in M.items():
        npf = f"{r['ablation_no_prefix_uk']['recall@5']:.3f}" if "ablation_no_prefix_uk" in r else "—"
        L.append(f"| {k} | {r['uk']['recall@5']:.3f} | {r['ablation_no_norm_uk']['recall@5']:.3f} | {npf} | "
                 f"{r['raw_norm_mean']} ± {r['raw_norm_std']} |")
    (DOCS / "sr10_tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
