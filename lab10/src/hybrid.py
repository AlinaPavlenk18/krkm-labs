"""Гібридний пошук: BM25 + dense, злиття RRF (k = 60), reranking cross-encoder, pre-filter (Результат 4).

Конфігурації (mode):
  bm25          — лише лексичний пошук (rank_bm25.BM25Okapi, токени зі стемінгом, common.tokenize);
  dense         — лише векторний (FAISS HNSW, index.HNSWStore);
  hybrid        — RRF над топ-30 BM25 і топ-30 dense: score(d) = Σ 1 / (k + rank_i(d)), k = 60;
  hybrid_rerank — топ-30 після RRF переранжовує cross-encoder; повертається новий порядок (топ-5 / топ-10).

Pre-filter за метаданими (type, sensitivity, дата) застосовується ДО ранжування: BM25 рахує
бали лише для дозволених фрагментів, FAISS обходить граф з IDSelector. Для порівняння є post-filter.
"""
import time

import numpy as np
from rank_bm25 import BM25Okapi

from common import SENSITIVITY_ORDER, tokenize
from index import build_store

RRF_K = 60
CANDIDATES = 30


def rrf(rank_lists, k=RRF_K):
    score = {}
    for lst in rank_lists:
        for r, i in enumerate(lst, start=1):
            score[i] = score.get(i, 0.0) + 1.0 / (k + r)
    return sorted(score.items(), key=lambda x: -x[1])


class Filters:

    def __init__(self, types=None, max_sensitivity=None, date_from=None, date_to=None):
        self.types, self.max_s, self.date_from, self.date_to = types, max_sensitivity, date_from, date_to

    def ok(self, c):
        if self.types and c["type"] not in self.types:
            return False
        if self.max_s and SENSITIVITY_ORDER[c["sensitivity"]] > SENSITIVITY_ORDER[self.max_s]:
            return False
        if self.date_from and c["date"] < self.date_from:
            return False
        if self.date_to and c["date"] > self.date_to:
            return False
        return True

    def __repr__(self):
        return f"Filters(types={self.types}, max_sensitivity={self.max_s}, date_from={self.date_from}, date_to={self.date_to})"


class HybridSearcher:
    def __init__(self, chunks, encoder, contexts=None, reranker=None, M=32, ef_construction=200, ef_search=64):
        """chunks — одиниці індексу; contexts — {chunk_id/parent_id: unit} для повернення контексту."""
        self.chunks = chunks
        self.contexts = contexts or {c["chunk_id"]: c for c in chunks}
        self.encoder, self.reranker = encoder, reranker
        t = time.perf_counter()
        self.bm25 = BM25Okapi([tokenize(c["embed_text"]) for c in chunks])
        self.bm25_build_seconds = time.perf_counter() - t
        t = time.perf_counter()
        self.vectors = encoder.encode_passages([c["embed_text"] for c in chunks])
        self.encode_seconds = time.perf_counter() - t
        self.store = build_store(chunks, self.vectors, M, ef_construction, ef_search)

    def allowed_ids(self, filters):
        if filters is None:
            return None
        return {i for i, c in enumerate(self.chunks) if filters.ok(c)}

    def bm25_rank(self, query, n=CANDIDATES, allowed=None):
        scores = self.bm25.get_scores(tokenize(query))
        if allowed is not None:
            mask = np.full(len(scores), -np.inf)
            idx = np.fromiter(allowed, dtype=int) if allowed else np.array([], dtype=int)
            mask[idx] = scores[idx]
            scores = mask
        order = np.argsort(-scores)[:n]
        return [(int(i), float(scores[i])) for i in order if np.isfinite(scores[i]) and scores[i] > 0]

    def dense_rank(self, query, n=CANDIDATES, allowed=None, qvec=None):
        q = self.encoder.encode_queries([query]) if qvec is None else qvec
        return self.store.search(q, n, allowed=allowed)[0]

    def search(self, query, mode="hybrid_rerank", k=10, filters=None, post_filter=False, timings=None):
        """Повертає список результатів [{rank, idx, chunk_id, context_id, score, ...}] довжини ≤ k.
        Для ієрархічної стратегії результати дедуплікуються за батьківським фрагментом."""
        t0 = time.perf_counter()
        allowed = None if post_filter else self.allowed_ids(filters)
        cand = {}
        if mode in ("bm25", "hybrid", "hybrid_rerank"):
            b = self.bm25_rank(query, CANDIDATES, allowed)
            cand["bm25"] = [i for i, _ in b]
            bscore = dict(b)
        t1 = time.perf_counter()
        if mode in ("dense", "hybrid", "hybrid_rerank"):
            d = self.dense_rank(query, CANDIDATES, allowed)
            cand["dense"] = [i for i, _ in d]
            dscore = dict(d)
        t2 = time.perf_counter()
        if mode == "bm25":
            ranked = b
        elif mode == "dense":
            ranked = d
        else:
            ranked = rrf([cand["bm25"], cand["dense"]])[:CANDIDATES]
        rerank_scores = None
        if mode == "hybrid_rerank" and ranked:
            ids = [i for i, _ in ranked]
            texts = [self.contexts.get(self.chunks[i].get("parent_id") or self.chunks[i]["chunk_id"],
                                       self.chunks[i])["text"] for i in ids]
            s = self.reranker.score(query, texts)
            order = np.argsort(-s)
            ranked = [(ids[j], float(s[j])) for j in order]
            rerank_scores = {ids[j]: float(s[j]) for j in order}
        t3 = time.perf_counter()
        if post_filter and filters is not None:
            ranked = [(i, sc) for i, sc in ranked if filters.ok(self.chunks[i])]
        out, seen = [], set()
        for i, sc in ranked:
            c = self.chunks[i]
            ctx = c.get("parent_id") or c["chunk_id"]
            if ctx in seen:
                continue
            seen.add(ctx)
            out.append({"rank": len(out) + 1, "idx": i, "chunk_id": c["chunk_id"], "context_id": ctx,
                        "doc_id": c["doc_id"], "score": sc,
                        "bm25_rank": cand.get("bm25", []).index(i) + 1 if i in cand.get("bm25", []) else None,
                        "dense_rank": cand.get("dense", []).index(i) + 1 if i in cand.get("dense", []) else None,
                        "rerank_score": rerank_scores.get(i) if rerank_scores else None})
            if len(out) == k:
                break
        if timings is not None:
            timings.append({"bm25_ms": (t1 - t0) * 1000, "dense_ms": (t2 - t1) * 1000,
                            "fuse_rerank_ms": (t3 - t2) * 1000, "total_ms": (time.perf_counter() - t0) * 1000})
        return out

    def context_text(self, hit):
        return self.contexts[hit["context_id"]]["text"]
