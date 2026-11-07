import time

import requests

from agent import config as C


def _fake(messages, tools):
    import re
    user = messages[-1]["content"]
    if tools:
        if "немає" not in user.split("Уже зібрані докази:")[1][:20]:
            return {"content": "ГОТОВО", "tool_calls": []}
        q = user.split("\n")[0].lower()
        if "перевантаж" in q:
            c = {"name": "graph_query", "args": {"template": "overloaded_substations"}}
        elif "пік" in q:
            c = {"name": "sql_metric", "args": {"metric": "peak_load", "by": ["region"]}}
        else:
            c = {"name": "search_docs", "args": {"query": q[9:80], "k": 3}}
        return {"content": "", "tool_calls": [c]}
    ids = re.findall(r"^\[([^\]]+)\]", user, re.M)
    return {"content": f"Відповідь за доказами [{ids[0]}]." if ids else "Не знаю: у наданих джерелах немає відповіді на це питання.",
            "tool_calls": []}


def chat(messages, tools=None, max_tokens=300):
    import os
    if os.environ.get("AGENT_FAKE_LLM") == "1":
        return {**_fake(messages, tools), "prompt_tokens": 100, "completion_tokens": 10, "ms": 1}
    body = {"model": C.MODEL, "messages": messages, "stream": False,
            "options": {"temperature": C.TEMPERATURE, "seed": C.SEED, "num_ctx": C.NUM_CTX, "num_predict": max_tokens}}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": n, "description": s["description"],
                                                           "parameters": s["parameters"]}} for n, s in tools.items()]
    t = time.perf_counter()
    r = requests.post(C.OLLAMA.rstrip("/") + "/api/chat", json=body, timeout=C.LIMITS["max_seconds"])
    r.raise_for_status()
    d = r.json()
    msg = d.get("message", {})
    calls = [{"name": c["function"]["name"], "args": c["function"].get("arguments") or {}} for c in msg.get("tool_calls") or []]
    return {"content": msg.get("content", ""), "tool_calls": calls,
            "prompt_tokens": d.get("prompt_eval_count", 0), "completion_tokens": d.get("eval_count", 0),
            "ms": round((time.perf_counter() - t) * 1000)}
