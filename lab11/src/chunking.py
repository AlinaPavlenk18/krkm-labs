"""Стратегії поділу документів на фрагменти (Результат 2).

Чотири стратегії, усі працюють з очищеними документами (data/clean/docs.jsonl):
  fixed         — фіксоване вікно N слів з перекриттям (структуру ігнорує);
  structural    — за заголовками/секціями; довгі секції ділить за абзацами, далі за реченнями;
  hierarchical  — «small-to-big»: індексуються малі дочірні фрагменти (~60 слів),
                  а пошук повертає батьківську секцію (контекст для генерації);
  semantic      — межа ставиться там, де косинусна схожість сусідніх речень падає
                  нижче перцентиля (потрібен encoder).

Кожен фрагмент: chunk_id, doc_id, title, section, text, embed_text, n_words, parent_id,
метадані документа (type, date, sensitivity, source_url, license) і strategy.
embed_text = «назва документа. секція. текст» для стратегій, що знають структуру,
і «назва документа. текст» для fixed/semantic (вони секцій не бачать).
"""
import re

import numpy as np

from common import word_count

PREFIX = {"structural": "", "fixed": "fix", "hierarchical": "ch", "semantic": "sem"}
META_KEYS = ["type", "date", "sensitivity", "source_url", "license", "origin"]

ABBR = ("м.", "вул.", "просп.", "кв.", "ст.", "р.", "рр.", "с.", "т.", "ін.", "напр.", "рис.", "Рис.", "табл.",
        "Табл.", "див.", "№", "пл.", "обл.", "і т.", "т. д.", "Vol.", "No.", "P.", "et al.", "ed.")
SENT_RE = re.compile(r"(?<=[.!?…])\s+(?=[«\"(A-ZА-ЩЬЮЯҐЄІЇ0-9])")
ADDRESS_RE = re.compile(r"\b(вул\.|просп\.|кв\.)\s*\S")


def split_sentences(text):
    parts = SENT_RE.split(text.replace("\n", " "))
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
       
        if out and (out[-1].endswith(ABBR) or re.search(r"(^|\s)[А-ЯҐЄІЇA-Z]\.$", out[-1])):
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def fragment_sensitivity(doc_sens, text):
    """C4: фрагмент успадковує рівень документа; адреса споживача піднімає його до restricted."""
    if doc_sens != "restricted" and ADDRESS_RE.search(text):
        return "restricted"
    return doc_sens


def _mk(doc, idx, section, text, strategy, parent_id=None, with_section=True):
    meta = {k: doc.get(k) for k in META_KEYS}
    meta["sensitivity"] = fragment_sensitivity(doc["sensitivity"], text)
    head = f"{doc['title']}. {section}. " if with_section and section != doc["title"] else f"{doc['title']}. "
    return {"chunk_id": f"{doc['doc_id']}#{PREFIX.get(strategy, strategy[:3])}{idx:03d}", "doc_id": doc["doc_id"], "title": doc["title"],
            "section": section, "text": text, "embed_text": head + text, "n_words": word_count(text),
            "parent_id": parent_id, "strategy": strategy, **meta,
            "doc_sensitivity": doc["sensitivity"]}


def _pack(units, max_words):
    """Жадібно пакує одиниці (абзаци/речення) у шматки до max_words слів."""
    out, cur, n = [], [], 0
    for u in units:
        w = word_count(u)
        if cur and n + w > max_words:
            out.append(" ".join(cur)); cur, n = [], 0
        if w > max_words: 
            sents = split_sentences(u)
            if len(sents) > 1:
                out.extend(_pack(sents, max_words)); continue
        cur.append(u); n += w
    if cur:
        out.append(" ".join(cur))
    return out

def chunk_fixed(docs, size=120, overlap=30):
    chunks = []
    for d in docs:
        words = " ".join(s["text"] for s in d["sections"]).split()
        step = size - overlap
        i = 0
        for start in range(0, max(1, len(words) - overlap), step):
            piece = " ".join(words[start:start + size])
            if piece:
                chunks.append(_mk(d, i, d["title"], piece, "fixed", with_section=False)); i += 1
    return chunks


def chunk_structural(docs, max_words=180, min_words=25):
    chunks = []
    for d in docs:
        i = 0
        pending = None  
        for s in d["sections"]:
            paras = [p for p in s["text"].split("\n\n") if p.strip()]
            pieces = _pack(paras, max_words)
            if pending:
                pieces[0] = pending[1] + " " + pieces[0]
                section = pending[0] + " / " + s["section"]
                pending = None
            else:
                section = s["section"]
            if len(pieces) == 1 and word_count(pieces[0]) < min_words:
                pending = (section, pieces[0]); continue
            for p in pieces:
                chunks.append(_mk(d, i, section, p, "structural")); i += 1
        if pending:
            chunks.append(_mk(d, i, pending[0], pending[1], "structural"))
    return chunks


def chunk_hierarchical(docs, child_words=60, parent_max_words=400):
    children, parents = [], []
    for d in docs:
        ci, pi = 0, 0
        for s in d["sections"]:
            paras = [p for p in s["text"].split("\n\n") if p.strip()]
            for ptext in _pack(paras, parent_max_words):
                parent = _mk(d, pi, s["section"], ptext, "hierarchical_parent")
                parent["chunk_id"] = f"{d['doc_id']}#par{pi:03d}"
                parents.append(parent); pi += 1
                for ctext in _pack(split_sentences(ptext), child_words):
                    ch = _mk(d, ci, s["section"], ctext, "hierarchical", parent_id=parent["chunk_id"])
                    children.append(ch); ci += 1
    return children, parents


def chunk_semantic(docs, encoder, percentile=20, min_words=40, max_words=200):
   
    chunks = []
    for d in docs:
        sents = [x for s in d["sections"] for x in split_sentences(s["text"])]
        if not sents:
            continue
        emb = encoder.encode_passages(sents)
        sims = np.sum(emb[:-1] * emb[1:], axis=1) if len(sents) > 1 else np.array([])
        thr = np.percentile(sims, percentile) if len(sims) else 0
        i, cur, n = 0, [sents[0]], word_count(sents[0])
        for j in range(1, len(sents)):
            w = word_count(sents[j])
            boundary = (sims[j - 1] < thr and n >= min_words) or n + w > max_words
            if boundary:
                chunks.append(_mk(d, i, d["title"], " ".join(cur), "semantic", with_section=False)); i += 1
                cur, n = [], 0
            cur.append(sents[j]); n += w
        chunks.append(_mk(d, i, d["title"], " ".join(cur), "semantic", with_section=False))
    return chunks


STRATEGIES = ["fixed", "structural", "hierarchical", "semantic"]


def build(strategy, docs, encoder=None, **kw):
    if strategy == "fixed":
        ch = chunk_fixed(docs, **kw); return ch, {c["chunk_id"]: c for c in ch}
    if strategy == "structural":
        ch = chunk_structural(docs, **kw); return ch, {c["chunk_id"]: c for c in ch}
    if strategy == "hierarchical":
        ch, par = chunk_hierarchical(docs, **kw); return ch, {p["chunk_id"]: p for p in par}
    if strategy == "semantic":
        ch = chunk_semantic(docs, encoder, **kw); return ch, {c["chunk_id"]: c for c in ch}
    raise ValueError(strategy)
