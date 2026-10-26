"""Результат 1. RAG-конвеєр із цитуванням і політикою «не знаю».

запит → гібридний пошук ЛР10 (BM25 + e5-small, RRF k = 60) з pre-filter за правами ролі → reranker cross-encoder
→ топ-k батьківських секцій (hierarchical) [+ підграф із графа знань, режим «text+graph»] → промпт prompts/<версія>.md
→ LLM (Ollama) → відповідь → перевірка цитат (усі [id] мають бути серед наданого контексту) → журнал logs/rag_log.jsonl.

Журнал (одна JSON-стрічка на запит): ts, request_id, role, mode, question, prompt_version, model, sources (id, doc_id,
score, sensitivity), graph (сутності, ID фактів), answer, citations, invalid_citations, uncited_sentences, abstained,
canary_leak, tokens (prompt / completion / total), latency_ms (retrieval / graph / llm / total), cost_usd.
"""
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import STUB, Settings, max_sensitivity
from llm import chat

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
LOGS = ROOT / "logs"
CANARY = "KH-CANARY-7Q2X"         
ABSTAIN_TEXT = "Не знаю: у наданих джерелах немає відповіді на це питання."
CITE_RE = re.compile(r"\[([^\[\]\s]{1,40})\]")


def load_prompt(version):
    raw = (PROMPTS / f"{version}.md").read_text(encoding="utf-8")
    system = raw.split("===SYSTEM===", 1)[1].split("===USER===", 1)[0].strip()
    user = raw.split("===USER===", 1)[1].strip()
    return system, user


def is_abstention(text):
    return text.strip().lower().startswith("не знаю")


def check_citations(answer, context_ids):
    cited = CITE_RE.findall(answer)
    invalid = sorted({c for c in cited if c not in context_ids})
    if is_abstention(answer):
        return cited, invalid, []
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[А-ЯҐЄІЇA-Z«(])", answer.strip()) if len(s.strip()) > 15]
    uncited = [s for s in sents if not CITE_RE.search(s) and "немає" not in s.lower()]
    return cited, invalid, uncited


REFUSAL_TEXT = "Не можу виконати цей запит: він суперечить правилам довідкової системи."


def _norm(t):
    return re.sub(r"\s+", " ", t).strip().lower()


def output_guard(text, system_text, context_ids, leak=True, uncited=False):
    flags = []
    out = text
    if leak:
        sys_n = _norm(system_text)
        sents = re.split(r"(?<=[.!?])\s+", text.strip())
        keep = []
        for snt in sents:
            core = _norm(CITE_RE.sub("", snt)).rstrip(".!? ")
            if CANARY.lower() in snt.lower() or (len(core) >= 25 and core in sys_n and not is_abstention(snt)):
                flags.append("leak")
                lead = re.match(r"^((?:\[[^\[\]\s]{1,40}\])+)", snt.strip())  
                if lead and keep:
                    keep[-1] = keep[-1] + " " + lead.group(1)
                continue
            keep.append(snt)
        if "leak" in flags:
            out = " ".join(keep).strip() or REFUSAL_TEXT
    if uncited and not is_abstention(out) and out != REFUSAL_TEXT:
        if not [c for c in CITE_RE.findall(out) if c in context_ids]:
            flags.append("uncited")
            out = ABSTAIN_TEXT
    return out, flags


class Retriever:

    def __init__(self, s: Settings):
        from common import CLEAN, read_jsonl
        import chunking
        from encoders import Encoder, Reranker
        from hybrid import HybridSearcher
        docs = read_jsonl(CLEAN / "docs.jsonl")
        units, contexts = chunking.build(s.strategy, docs)
        self.searcher = HybridSearcher(units, Encoder(s.embed_model), contexts=contexts, reranker=Reranker(s.reranker))
        self.contexts = contexts
        self.units = units
        self.max_words = s.max_source_words

    def search(self, question, role, k, mode="hybrid_rerank"):
        from hybrid import Filters
        hits = self.searcher.search(question, mode=mode, k=k, filters=Filters(max_sensitivity=max_sensitivity(role)))
        out = []
        for h in hits:
            c = self.contexts[h["context_id"]]
            out.append({"id": h["context_id"], "doc_id": c["doc_id"], "title": c["title"], "section": c["section"],
                        "date": c["date"], "sensitivity": c["sensitivity"],
                        "text": self.window(c["text"], self.units[h["idx"]]["text"], self.max_words),
                        "score": round(float(h["score"]), 4)})
        return out

    @staticmethod
    def window(parent, child, max_words):
        """Вікно до max_words слів навколо знайденого дочірнього фрагмента (≈ 20 % слів — контекст перед ним)."""
        words = parent.split()
        if len(words) <= max_words:
            return parent
        pos = parent.find(child[:60])
        start_w = len(parent[:pos].split()) if pos >= 0 else 0
        a = max(0, min(start_w - max_words // 5, len(words) - max_words))
        return ("… " if a > 0 else "") + " ".join(words[a:a + max_words]) + (" …" if a + max_words < len(words) else "")

    def get(self, cid):
        return self.contexts.get(cid)


def format_context(sources, graph_text=""):
    lines = [f"[{s['id']}] ({s['title']}; {s['section']}; {s['date']}) {s['text']}" for s in sources]
    if graph_text:
        lines.append("Факти з графа знань (вузол «опис» —ЗВ'ЯЗОК→ вузол):")
        lines.append(graph_text)
    return "\n".join(lines)


class RAG:
    def __init__(self, settings: Settings = None, retriever: Retriever = None, graph=None, log_path=None):
        self.s = settings or Settings()
        self.retriever = retriever or Retriever(self.s)
        self.graph = graph            # GraphContext або None (тоді режим text+graph недоступний)
        self.log_path = Path(log_path or LOGS / "rag_log.jsonl")

    def answer(self, question, role="analyst", mode="text", top_k=None, extra_sources=None, log=True, tag=None):
        s = self.s
        k = top_k or s.top_k
        t0 = time.perf_counter()
        sources = self.retriever.search(question, role, k)
        t1 = time.perf_counter()
        for x in extra_sources or []:                  
            sources.append(x)
        graph = {"entities": [], "facts": [], "text": ""}
        if mode == "text+graph" and self.graph is not None:
            graph = self.graph.build(question, role)
        t2 = time.perf_counter()
        context_ids = {x["id"] for x in sources} | {f["id"] for f in graph["facts"]}
        system, user_tpl = load_prompt(s.prompt_version)
        system = system.replace("{canary}", CANARY)
        user = (user_tpl.replace("{context}", format_context(sources, graph["text"]) or "(джерел немає)")
                .replace("{question}", question))
        if not sources and not graph["facts"]:
            # політика «не знаю» на рівні пошуку: для ролі не знайдено жодного дозволеного джерела
            text, pt, ct, llm_ms, model = ABSTAIN_TEXT, 0, 0, 0.0, "none"
        else:
            r = chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                     provider=s.gen_provider, base_url=s.gen_base_url, model=s.gen_model, api_key=s.gen_api_key,
                     temperature=s.temperature, seed=s.seed, max_tokens=s.max_tokens, num_ctx=s.gen_num_ctx)
            text, pt, ct, llm_ms, model = r.text, r.prompt_tokens, r.completion_tokens, r.latency_ms, r.model
        raw_text = text
        text, guard_flags = output_guard(text, system, context_ids, leak=s.guard_leak, uncited=s.guard_uncited)
        cited, invalid, uncited = check_citations(text, context_ids)
        total_ms = (time.perf_counter() - t0) * 1000
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "request_id": uuid.uuid4().hex[:12],
            "tag": tag, "role": role, "mode": mode, "question": question, "prompt_version": s.prompt_version,
            "model": model, "top_k": k, "stub": STUB,
            "sources": [{"id": x["id"], "doc_id": x["doc_id"], "score": x.get("score"), "sensitivity": x["sensitivity"]} for x in sources],
            "graph": {"entities": graph["entities"], "facts": [f["id"] for f in graph["facts"]], "backend": graph.get("backend")},
            "answer": text, "citations": cited, "invalid_citations": invalid, "uncited_sentences": uncited,
            "abstained": is_abstention(text), "canary_leak": CANARY in text,
            "raw_answer": raw_text if guard_flags else None, "guard": guard_flags, "canary_leak_raw": CANARY in raw_text,
            "tokens": {"prompt": pt, "completion": ct, "total": pt + ct},
            "latency_ms": {"retrieval": round((t1 - t0) * 1000, 1), "graph": round((t2 - t1) * 1000, 1),
                           "llm": round(llm_ms, 1), "total": round(total_ms, 1)},
            "cost_usd": round(pt / 1e6 * s.price_in_per_m + ct / 1e6 * s.price_out_per_m, 6),
        }
        if log:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        rec["_sources_full"] = sources
        rec["_graph_full"] = graph
        rec["_prompt"] = {"system_chars": len(system), "user": user}
        return rec
