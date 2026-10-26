"""Клієнти LLM: генератор (Ollama /api/chat або OpenAI-сумісний /chat/completions) і суддя.

Повертають LLMResult: text, prompt_tokens, completion_tokens, latency_ms, model.
Для Ollama використовується рідний /api/chat, бо лише там можна задати num_ctx: інакше довгий промпт
мовчки обрізається до стандартного вікна. temperature = 0 і seed = 42 — для відтворюваності.
LAB11_STUB=1 — детермінована заглушка (без мережі) для перевірки коду.
"""
import json
import re
import time
from dataclasses import dataclass

import requests

from config import STUB


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    model: str


class LLMError(RuntimeError):
    pass


def _approx_tokens(text):
    return max(1, round(len(text) / 3.2)) 


def chat(messages, *, provider, base_url, model, api_key="", temperature=0.0, seed=42, max_tokens=400,
         num_ctx=8192, timeout=600, retries=4, extra=None):
    if STUB:
        return _stub(messages, model)
    t = time.perf_counter()
    for attempt in range(retries):
        try:
            if provider == "ollama":
                r = requests.post(base_url.rstrip("/") + "/api/chat", timeout=timeout, json={
                    "model": model, "messages": messages, "stream": False,
                    "options": {"temperature": temperature, "seed": seed, "num_ctx": num_ctx, "num_predict": max_tokens}})
            else:
                r = requests.post(base_url.rstrip("/") + "/chat/completions", timeout=timeout,
                                  headers={"Authorization": f"Bearer {api_key}"},
                                  json={"model": model, "messages": messages, "temperature": temperature,
                                        "seed": seed, "max_tokens": max_tokens, **(extra or {})})
            if r.status_code == 429 or r.status_code >= 500:    
                ra = r.headers.get("retry-after")
                time.sleep(min(90, float(ra) + 1) if ra and ra.replace(".", "").isdigit() else min(60, 5 * 2 ** attempt))
                continue
            if r.status_code != 200:
                raise LLMError(f"{provider} {r.status_code}: {r.text[:300]}")
            d = r.json()
            break
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise LLMError(f"{provider} недоступний: {e}") from e
            time.sleep(3)
    else:
        raise LLMError(f"{provider}: вичерпано спроби (429/5xx)")
    ms = (time.perf_counter() - t) * 1000
    prompt_text = " ".join(m["content"] for m in messages)
    if provider == "ollama":
        text = d.get("message", {}).get("content", "")
        pt, ct = d.get("prompt_eval_count"), d.get("eval_count")
    else:
        text = d["choices"][0]["message"]["content"] or ""
        u = d.get("usage") or {}
        pt, ct = u.get("prompt_tokens"), u.get("completion_tokens")
    return LLMResult(text.strip(), int(pt or _approx_tokens(prompt_text)), int(ct or _approx_tokens(text)), ms, model)

def _stub(messages, model):
    """Генератор-заглушка: відповідає першим реченням першого джерела з цитатою; без джерел — «Не знаю».
    Суддя-заглушка: повертає JSON, вважаючи підтвердженими речення, що мають валідні цитати."""
    sys_msg, user = messages[0]["content"], messages[-1]["content"]
    if "ОЦІНЮВАННЯ" in sys_msg:
        ids = set(re.findall(r"^\[([^\]]+)\]", user, flags=re.M))
        ans = user.split("ВІДПОВІДЬ:", 1)[-1]
        sents = [s for s in re.split(r"(?<=[.!?])\s+", ans.strip()) if s]
        claims = [{"claim": s[:80], "supported": bool(set(re.findall(r"\[([^\]]+)\]", s)) & ids),
                   "cited_ok": bool(set(re.findall(r"\[([^\]]+)\]", s)) & ids)} for s in sents]
        out = json.dumps({"claims": claims, "comment": "stub"}, ensure_ascii=False)
        return LLMResult(out, _approx_tokens(user), _approx_tokens(out), 5.0, "stub-judge")
    blocks = re.findall(r"^\[([^\]]+)\]\s*(?:\([^)]*\)\s*)?(.+)$", user, flags=re.M)
    q = user.split("ПИТАННЯ:", 1)[-1].strip().lower()
    if not blocks or any(w in q for w in ["ціна", "тариф", "керівника", "погода завтра", "wind", "сонячних", "релейний", "грудень"]):
        text = "Не знаю: у наданих джерелах немає відповіді на це питання."
    else:
        cid, body = blocks[0]
        first = re.split(r"(?<=[.!?])\s+", body.strip())[0]
        text = f"{first} [{cid}]"
    return LLMResult(text, _approx_tokens(user), _approx_tokens(text), 12.0, "stub-gen")
