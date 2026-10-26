import json
from urllib.parse import quote
import os
import sys
from pathlib import Path

os.environ.setdefault("LAB11_STUB", "1")
os.environ.setdefault("GRAPH_BACKEND", "csv")
os.environ["RATE_LIMIT_PER_MIN"] = "5"
os.environ["LAB11_API_KEYS"] = json.dumps({"k-ext": "external", "k-an": "analyst", "k-disp": "dispatcher"})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  
from fastapi.testclient import TestClient  

from api.main import STATE, app  


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_limits():
    if STATE:
        STATE["hits"].clear()


def ask(c, key, **body):
    h = {"X-API-Key": key} if key else {}
    return c.post("/ask", json={"question": "Що робити диспетчеру при навантаженні понад 95 %?", **body}, headers=h)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ask_ok_with_citations(client):
    r = ask(client, "k-an")
    assert r.status_code == 200
    d = r.json()
    assert d["role"] == "analyst" and d["sources"] and d["citations"] and not d["invalid_citations"]


def test_text_graph_mode(client):
    r = client.post("/ask", json={"question": "Які підстанції живить підстанція №1?", "mode": "text+graph"}, headers={"X-API-Key": "k-an"})
    assert r.status_code == 200 and r.json()["graph_facts"]


def test_no_key_401(client):
    assert ask(client, None).status_code == 401


def test_bad_key_401(client):
    assert ask(client, "wrong").status_code == 401


@pytest.mark.parametrize("body", [{"question": "аб"}, {"question": "x" * 501}, {"mode": "graph"}, {"top_k": 0}, {"top_k": 11}, {"extra": 1}])
def test_validation_422(client, body):
    assert ask(client, "k-an", **body).status_code == 422


def test_rate_limit_429(client):
    codes = [ask(client, "k-ext").status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_rate_limit_retry_after(client):
    for _ in range(5):
        ask(client, "k-ext")
    r = ask(client, "k-ext")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_external_sees_only_public(client):
    d = ask(client, "k-ext").json()
    assert all(s["sensitivity"] == "public" for s in d["sources"])


def test_analyst_never_gets_restricted(client):
    d = client.post("/ask", json={"question": "Адреси споживачів у реєстрі"}, headers={"X-API-Key": "k-an"}).json()
    assert all(s["sensitivity"] != "restricted" for s in d["sources"])


def test_source_access_by_role(client):
    restricted = next(cid for cid, c in STATE["rag"].retriever.contexts.items() if c["sensitivity"] == "restricted")
    assert client.get(f"/sources/{quote(restricted, safe='')}", headers={"X-API-Key": "k-an"}).status_code == 403
    assert client.get(f"/sources/{quote(restricted, safe='')}", headers={"X-API-Key": "k-disp"}).status_code == 200


def test_source_404(client):
    assert client.get("/sources/nope%23par999", headers={"X-API-Key": "k-an"}).status_code == 404


def test_llm_down_503(client, monkeypatch):
    import rag
    from llm import LLMError

    def boom(*a, **k):
        raise LLMError("down")
    monkeypatch.setattr(rag, "chat", boom)
    assert ask(client, "k-an").status_code == 503
