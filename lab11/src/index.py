"""Векторний індекс FAISS HNSW з оновленням (Результат 3).

Індекс: IndexIDMap2(IndexHNSWFlat(d, M, METRIC_INNER_PRODUCT)) на нормалізованих векторах,
тобто скалярний добуток = косинусна схожість. IndexIDMap2 дає власні 64-бітні id фрагментів.

Оновлення. HNSW у FAISS не підтримує remove_ids (граф не вміє коректно видаляти вершини),
тому використано схему «надгробків» (tombstones):
  delete(doc_id)  — усі вектори документа позначаються видаленими й виключаються з пошуку
                    через IDSelector (фільтр під час обходу графа, а не після);
  upsert(doc, chunks) — старі фрагменти документа видаляються (tombstone), нові додаються з новими id;
  compact()       — повна перебудова індексу без надгробків (коли їх > 20 % або за розкладом).
Той самий IDSelector використовується для pre-filter за метаданими (Результат 4).
"""
import time

import faiss
import numpy as np


class HNSWStore:
    def __init__(self, dim, M=32, ef_construction=200, ef_search=64):
        self.dim, self.M, self.efc, self.efs = dim, M, ef_construction, ef_search
        self._new_index()
        self.meta = {}           # int id -> chunk dict (без вектора)
        self.vectors = {}        # int id -> vector (потрібні для compact)
        self.doc_ids = {}        # doc_id -> [int id]
        self.deleted = set()
        self.next_id = 0
        self.build_seconds = 0.0

    def _new_index(self):
        base = faiss.IndexHNSWFlat(self.dim, self.M, faiss.METRIC_INNER_PRODUCT)
        base.hnsw.efConstruction = self.efc
        self.index = faiss.IndexIDMap2(base)

    def add(self, chunks, vectors):
        ids = np.arange(self.next_id, self.next_id + len(chunks), dtype="int64")
        self.next_id += len(chunks)
        t = time.perf_counter()
        self.index.add_with_ids(np.ascontiguousarray(vectors, dtype="float32"), ids)
        self.build_seconds += time.perf_counter() - t
        for i, c, v in zip(ids, chunks, vectors):
            i = int(i)
            self.meta[i] = c
            self.vectors[i] = v
            self.doc_ids.setdefault(c["doc_id"], []).append(i)
        return ids

    def live_ids(self):
        return [i for i in self.meta if i not in self.deleted]

    def search(self, qvecs, k=10, allowed=None, ef_search=None):
        """allowed — множина int id, серед яких шукати (pre-filter); None = усі живі."""
        if allowed is None:
            allowed = None if not self.deleted else set(self.live_ids())
        else:
            allowed = set(allowed) - self.deleted
        params = faiss.SearchParametersHNSW()
        params.efSearch = max(ef_search or self.efs, k)
        if allowed is not None:
            sel_ids = np.fromiter(allowed, dtype="int64")
            params.sel = faiss.IDSelectorBatch(sel_ids)
        q = np.ascontiguousarray(np.atleast_2d(qvecs), dtype="float32")
        D, I = self.index.search(q, k, params=params)
        return [[(int(i), float(d)) for i, d in zip(Ir, Dr) if i >= 0] for Ir, Dr in zip(I, D)]

    def delete(self, doc_id):
        ids = self.doc_ids.pop(doc_id, [])
        self.deleted.update(ids)
        return ids

    def upsert(self, doc_id, chunks, vectors):
        old = self.delete(doc_id)
        new = self.add(chunks, vectors) if len(chunks) else []
        return old, [int(i) for i in new]

    def tombstone_ratio(self):
        return len(self.deleted) / max(1, len(self.meta))

    def compact(self):
        """Перебудова без видалених векторів; id живих фрагментів зберігаються."""
        live = sorted(self.live_ids())
        self._new_index()
        if live:
            t = time.perf_counter()
            self.index.add_with_ids(np.stack([self.vectors[i] for i in live]).astype("float32"),
                                    np.array(live, dtype="int64"))
            self.build_seconds = time.perf_counter() - t
        for i in list(self.deleted):
            self.meta.pop(i, None); self.vectors.pop(i, None)
        self.deleted.clear()

    def __len__(self):
        return len(self.meta) - len(self.deleted)


def build_store(chunks, vectors, M=32, ef_construction=200, ef_search=64):
    s = HNSWStore(vectors.shape[1], M, ef_construction, ef_search)
    t = time.perf_counter()
    s.add(chunks, vectors)
    s.build_seconds = time.perf_counter() - t
    return s


def exact_topk(vectors, qvecs, k):
    sims = np.atleast_2d(qvecs) @ vectors.T
    return np.argsort(-sims, axis=1)[:, :k]
