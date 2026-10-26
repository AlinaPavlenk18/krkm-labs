"""Результат 4. LLM-as-a-judge: faithfulness і точність цитат за рубрикою prompts/judge_v1.md.

Правила захисту даних: суддя — зовнішній хмарний сервіс, тому
  * фрагменти з sensitivity = restricted йому НЕ передаються (рядок замінюється позначкою «[вилучено]»), а
    оцінювання загалом ведеться від ролі analyst, де restricted у контекст і не потрапляє;
  * API-ключ береться лише зі змінної JUDGE_API_KEY.
faithfulness = частка підтверджених тверджень; citation_accuracy (суддя) = частка тверджень із правильною цитатою.
"""
import json
import re

from config import Settings
from llm import chat
from rag import PROMPTS, format_context


class JudgeError(RuntimeError):
    pass


def load_judge_prompt(version="judge_v1"):
    raw = (PROMPTS / f"{version}.md").read_text(encoding="utf-8")
    return raw.split("===SYSTEM===", 1)[1].split("===USER===", 1)[0].strip(), raw.split("===USER===", 1)[1].strip()


def safe_sources(sources, external=True):
    if not external:
        return list(sources), 0
    keep = [s for s in sources if s.get("sensitivity") != "restricted"]
    return keep, len(sources) - len(keep)


def parse_json(text):
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise JudgeError(f"суддя повернув не JSON: {text[:200]}")
    return json.loads(m.group(0))


def judge(question, answer, sources, graph_text="", s: Settings = None, version="judge_v1"):
    s = s or Settings()
    if not s.judge_model and not _stub():
        raise JudgeError("не задано JUDGE_MODEL / JUDGE_BASE_URL / JUDGE_API_KEY")
    srcs, removed = safe_sources(sources, s.judge_is_external)
    system, tpl = load_judge_prompt(version)
    user = (tpl.replace("{context}", format_context(srcs, graph_text) or "(джерел немає)")
            .replace("{question}", question).replace("{answer}", answer))
    r = chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
             provider="openai", base_url=s.judge_base_url, model=s.judge_model, api_key=s.judge_api_key,
             temperature=0.0, seed=s.seed, max_tokens=2000, retries=8, extra=json.loads(s.judge_extra) if s.judge_extra else None)
    try:
        d = parse_json(r.text)
    except (JudgeError, json.JSONDecodeError):
        d = {"claims": [], "parse_error": True}
    claims = d.get("claims") or []
    n = len(claims)
    return {
        "judge_model": r.model, "judge_version": version, "removed_restricted": removed,
        "claims": claims, "n_claims": n,
        "faithfulness": (sum(bool(c.get("supported")) for c in claims) / n) if n else None,
        "citation_accuracy_judge": (sum(bool(c.get("cited_ok")) for c in claims) / n) if n else None,
        "conflict_noted": bool(d.get("conflict_noted")), "followed_injection": bool(d.get("followed_injection")),
        "comment": d.get("comment", ""), "parse_error": bool(d.get("parse_error")),
        "raw": r.text, "tokens": {"prompt": r.prompt_tokens, "completion": r.completion_tokens}, "latency_ms": round(r.latency_ms, 1),
    }


def _stub():
    from config import STUB
    return STUB
