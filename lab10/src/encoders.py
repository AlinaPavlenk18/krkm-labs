"""Моделі embeddings і reranker (локально, через sentence-transformers).

Конфігурація моделей — у MODELS. Ембедінги кешуються в results/cache/*.npy (ключ — хеш текстів),
тож повторні запуски не перераховують корпус.

Для перевірки конвеєра без завантаження моделей є заглушка: змінна середовища LAB10_STUB=1
(TF-IDF на символьних n-грамах + SVD). Результати із заглушкою НЕ використовуються у звіті.
"""
import hashlib
import os
import time

import numpy as np

from common import CACHE, SEED

MODELS = {
    # ключ: (назва на Hugging Face, префікс запиту, префікс документа, примітка)
    "e5-small": ("intfloat/multilingual-e5-small", "query: ", "passage: ", "багатомовна, 384 вим., до 512 токенів"),
    "ml-minilm": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "", "", "багатомовна, 384 вим., до 128 токенів"),
    "en-minilm": ("sentence-transformers/all-MiniLM-L6-v2", "", "", "англомовна (контроль мови), 384 вим., до 256 токенів"),
}
RERANKERS = {
    "mmarco": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "bge-m3": "BAAI/bge-reranker-v2-m3",
}

STUB = os.environ.get("LAB10_STUB") == "1"


class Encoder:
    def __init__(self, key, device="cpu"):
        self.key = key
        self.hf_name, self.qp, self.pp, self.note = MODELS[key]
        self.load_seconds = 0.0
        if STUB:
            self.model = None
            self.dim = 128
            return
        from sentence_transformers import SentenceTransformer
        t = time.perf_counter()
        self.model = SentenceTransformer(self.hf_name, device=device)
        self.load_seconds = time.perf_counter() - t
        get_dim = getattr(self.model, "get_embedding_dimension", None) or getattr(self.model, "get_sentence_embedding_dimension")
        self.dim = get_dim()
        self.max_seq_length = self.model.max_seq_length

    
    _stub_vec = None

    def _stub(self, texts):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        if Encoder._stub_vec is None:
            from common import read_jsonl, DATA
            corpus = [c["text"] for c in read_jsonl(DATA / "corpus.jsonl")]
            v = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True).fit(corpus)
            svd = TruncatedSVD(128, random_state=SEED).fit(v.transform(corpus))
            Encoder._stub_vec = (v, svd)
        v, svd = Encoder._stub_vec
        x = svd.transform(v.transform(texts)).astype("float32")
        return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)
    
    def _encode(self, texts, prefix, batch_size=32):
        if STUB:
            return self._stub(texts)
        return self.model.encode([prefix + t for t in texts], batch_size=batch_size, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False).astype("float32")

    def encode_passages(self, texts, cache=True):
        if not cache:
            return self._encode(texts, self.pp)
        h = hashlib.sha1(("\u0001".join(texts) + self.key + str(STUB)).encode("utf-8")).hexdigest()[:16]
        path = CACHE / f"{self.key}_{h}.npy"
        if path.exists():
            return np.load(path)
        CACHE.mkdir(parents=True, exist_ok=True)
        x = self._encode(texts, self.pp)
        np.save(path, x)
        return x

    def encode_queries(self, texts):
        return self._encode(texts, self.qp)


class Reranker:
    def __init__(self, key="mmarco", device="cpu"):
        self.key = key
        self.hf_name = RERANKERS[key]
        if STUB:
            self.model = None
            return
        from sentence_transformers import CrossEncoder
        t = time.perf_counter()
        self.model = CrossEncoder(self.hf_name, device=device, max_length=512)
        self.load_seconds = time.perf_counter() - t

    def score(self, query, texts):
        if STUB:  
            from common import tokenize
            q = set(tokenize(query))
            return np.array([len(q & set(tokenize(t))) / (len(q) + 1) for t in texts], dtype="float32")
        return np.asarray(self.model.predict([(query, t) for t in texts], batch_size=16, show_progress_bar=False),
                          dtype="float32")
