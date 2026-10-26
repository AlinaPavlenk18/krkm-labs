"""Результат 3. REST API чат-бота (FastAPI).

Ендпоїнти:
  GET  /health                 — стан сервісу (без автентифікації; без секретів);
  POST /ask                    — питання → відповідь з цитатами (заголовок X-API-Key обов'язковий);
  GET  /sources/{source_id}    — повний текст фрагмента, якщо його рівень конфіденційності дозволений ролі.
Автентифікація й ролі: X-API-Key → роль (external → public, analyst → internal, dispatcher/admin → restricted).
Ключі задаються ЛИШЕ поза кодом: змінна LAB11_API_KEYS='{"ключ": "роль", ...}' або файл api/keys.json (у .gitignore).
Обмеження частоти: RATE_LIMIT_PER_MIN запитів /ask на ключ за 60 с (типово 10), понад ліміт — 429 + Retry-After.
Валідація (Pydantic): question 3–500 символів, mode ∈ {text, text+graph}, top_k 1–10, зайві поля заборонені → 422.
Помилки: 401 (немає / хибний ключ), 403 (джерело вищого рівня), 404, 422, 429, 503 (LLM або Neo4j недоступні).
Запуск: uvicorn api.main:app --port 8000   (з каталогу lab11)
"""
import json
import os
import sys
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config import ROLES, STUB, Settings, allowed  
from llm import LLMError  

RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))
WINDOW_S = 60
STATE = {}


def load_keys():
    raw = os.environ.get("LAB11_API_KEYS")
    if not raw and (ROOT / "api" / "keys.json").exists():
        raw = (ROOT / "api" / "keys.json").read_text(encoding="utf-8")
    keys = json.loads(raw) if raw else {}
    bad = {k: r for k, r in keys.items() if r not in ROLES}
    if bad:
        raise RuntimeError(f"невідомі ролі в ключах: {sorted(set(bad.values()))}")
    return keys


@asynccontextmanager
async def lifespan(app):
    from rag import RAG
    s = Settings()
    graph, graph_err = None, None
    try:
        from graph_context import GraphContext
        graph = GraphContext(hops=s.graph_hops, max_facts=s.graph_max_facts)
    except Exception as e:                    
        graph_err = str(e)[:200]
    STATE.update(settings=s, rag=RAG(s, graph=graph, log_path=ROOT / "logs" / "api_log.jsonl"), keys=load_keys(), graph_err=graph_err,
                 hits=defaultdict(deque), lock=threading.Lock())
    yield
    STATE.clear()


app = FastAPI(title="Domain Knowledge Hub — чат-бот (ЛР11)", version="1.0.0", lifespan=lifespan,
              description="RAG + граф знань для прогнозування енергоспоживання. Відповіді лише з джерел, з цитатами [id].")


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=3, max_length=500, description="Питання українською")
    mode: Literal["text", "text+graph"] = "text"
    top_k: int = Field(5, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v):
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("питання порожнє")
        return v


class Source(BaseModel):
    id: str
    title: str
    section: str
    date: str
    sensitivity: str


class AskResponse(BaseModel):
    request_id: str
    role: str
    mode: str
    answer: str
    citations: list[str]
    invalid_citations: list[str]
    abstained: bool
    sources: list[Source]
    graph_facts: list[str]
    tokens: dict
    latency_ms: dict


def get_role(x_api_key: str | None = Header(default=None)):
    if not x_api_key:
        raise HTTPException(401, "потрібен заголовок X-API-Key", headers={"WWW-Authenticate": "API-Key"})
    role = STATE["keys"].get(x_api_key)
    if role is None:
        raise HTTPException(401, "невідомий API-ключ", headers={"WWW-Authenticate": "API-Key"})
    return x_api_key, role


def rate_limit(auth=Depends(get_role)):
    key, role = auth
    now = time.monotonic()
    with STATE["lock"]:
        q = STATE["hits"][key]
        while q and now - q[0] >= WINDOW_S:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            retry = max(1, int(WINDOW_S - (now - q[0])) + 1)
            raise HTTPException(429, f"перевищено ліміт {RATE_LIMIT} запитів за {WINDOW_S} с", headers={"Retry-After": str(retry)})
        q.append(now)
    return role


@app.exception_handler(LLMError)
async def llm_down(request: Request, exc: LLMError):
    return JSONResponse(status_code=503, content={"detail": "генератор (LLM) тимчасово недоступний"}, headers={"Retry-After": "30"})


@app.get("/health")
def health():
    s = STATE["settings"]
    rag = STATE["rag"]
    return {"status": "ok", "model": s.gen_model, "prompt_version": s.prompt_version, "stub": STUB,
            "graph": rag.graph.graph.name if rag.graph else None, "graph_error": STATE["graph_err"] is not None}


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, role: str = Depends(rate_limit)):
    rag = STATE["rag"]
    if body.mode == "text+graph" and rag.graph is None:
        raise HTTPException(503, "граф знань недоступний; спробуйте mode = text", headers={"Retry-After": "30"})
    r = rag.answer(body.question, role=role, mode=body.mode, top_k=body.top_k, tag="api")
    return AskResponse(request_id=r["request_id"], role=role, mode=body.mode, answer=r["answer"], citations=r["citations"],
                       invalid_citations=r["invalid_citations"], abstained=r["abstained"],
                       sources=[Source(**{k: x[k] for k in ("id", "title", "section", "date", "sensitivity")}) for x in r["_sources_full"]],
                       graph_facts=[f["text"] for f in r["_graph_full"]["facts"]], tokens=r["tokens"], latency_ms=r["latency_ms"])


@app.get("/sources/{source_id}")
def source(source_id: str, auth=Depends(get_role)):
    _, role = auth
    c = STATE["rag"].retriever.get(source_id)
    if c is None:
        raise HTTPException(404, "джерело не знайдено")
    if not allowed(c["sensitivity"], role):
        raise HTTPException(403, f"рівень «{c['sensitivity']}» недоступний для ролі «{role}»")
    return {"id": source_id, "doc_id": c["doc_id"], "title": c["title"], "section": c["section"], "date": c["date"],
            "sensitivity": c["sensitivity"], "text": c["text"]}
