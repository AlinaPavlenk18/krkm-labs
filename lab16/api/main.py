"""REST API демонстратора (FastAPI): рекомендації, пояснення, холодний старт і агент ЛР15.
  uvicorn api.main:app --port 8000        (з каталогу lab16)
"""
import sys
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from reco.cli import NOW, scores, setup
from reco.data import REPO, load_items, zone
from reco.eval import profile, rrf
from reco.explain import explain
from reco.models import Filters, _top

app = FastAPI(title="Domain Knowledge Hub — «Прогнозування енергоспоживання»", version="lab16")


@lru_cache(maxsize=1)
def state():
    return setup()


def card(i):
    it = load_items()[i]
    return {"id": i, "title": it["title"], "section": it["section"], "date": it["date"], "sensitivity": it["sensitivity"],
            "verified": it["verified"], "snippet": it["text"][:240] if it["sensitivity"] != "restricted" else None}


@app.get("/health")
def health():
    users, *_ = state()
    return {"status": "ok", "items": len(load_items()), "users": len(users)}


@app.get("/users")
def users_list():
    users, *_ = state()
    return [{"user_id": u, "role": v["role"], "group": v["group"], "cold": v["cold"] == "1"} for u, v in users.items()]


@app.get("/recommend")
def recommend(user_id: str, method: str = "hybrid", k: int = 5, role: str | None = None, verified_only: bool = True,
              max_age_days: int | None = None, with_explanations: bool = False):
    users, hist, models, w, kk = state()
    if user_id not in users:
        raise HTTPException(404, "невідомий користувач")
    if method not in ("hybrid", "graph", "embedding", "popularity"):
        raise HTTPException(400, "method: hybrid | graph | embedding | popularity")
    u = users[user_id]
    r = role or u["role"]
    ctx = {"role": r, "history": hist[user_id], "now": NOW, "profile": [] if hist[user_id] else profile(u)}
    flt = Filters(r, verified_only=verified_only, max_age_days=max_age_days,
                  zone=zone(u["group"]) if r == "dispatcher" and u["role"] == "dispatcher" else ())
    s, dropped = flt.apply(scores(models, method, ctx, w, kk), {i for i, _ in ctx["history"]}, NOW)
    top = _top(s, k)
    hist_items = [i for i, _ in sorted(ctx["history"], key=lambda x: x[1])]
    out = []
    for i in top:
        c = card(i)
        if with_explanations:
            e = explain(i, hist_items, ctx["profile"])
            c["explanation"], c["explanation_source"], c["path"] = e["final"], e["source"], e["path"]
        out.append(c)
    return {"user_id": user_id, "role": r, "method": method, "cold_start": not hist[user_id], "filtered_out": dict(dropped),
            "items": out}


class Cold(BaseModel):
    role: str = "dispatcher"
    group: str = "Dispatcher_2"
    k: int = 5


@app.post("/recommend/cold")
def recommend_cold(req: Cold):
    _, _, models, *_ = state()
    prof = profile({"role": req.role, "group": req.group})
    ctx = {"role": req.role, "history": [], "now": NOW, "profile": prof}
    s, _ = Filters(req.role).apply(rrf({n: m.scores(ctx) for n, m in models.items()},
                                       {"graph": 1, "embedding": 1, "popularity": 1}, 60), set(), NOW)
    return {"profile": prof, "items": [card(i) | {"explanation": explain(i, (), prof)["final"]} for i in _top(s, req.k)]}


class Ask(BaseModel):
    question: str


@app.post("/ask")
def ask(req: Ask):
    """Агент ЛР15 (LangGraph, захисти увімкнено). Потрібна Ollama з qwen2.5:7b (GEN_BASE_URL)."""
    sys.path.insert(0, str(REPO / "lab15"))
    from agent.graph import ask as agent_ask
    rec = agent_ask(req.question, "lab16_api")
    return {"answer": rec["answer"], "citations": rec["citations"], "blocked": rec["blocked"], "totals": rec["totals"],
            "tools": [s["tool"] for s in rec["steps"] if s["node"] == "retrieve" and "tool" in s and "rejected" not in s]}
