"""Налаштування ЛР11. Усе, що залежить від середовища, — лише зі змінних середовища (ключів у коді немає).

Генератор (локально, Ollama):
  GEN_PROVIDER=ollama          GEN_BASE_URL=http://localhost:11434     GEN_MODEL=qwen2.5:7b
Суддя (інша модель, OpenAI-сумісний хмарний API, напр. Groq або Gemini):
  JUDGE_BASE_URL=https://api.groq.com/openai/v1   JUDGE_MODEL=openai/gpt-oss-120b   JUDGE_API_KEY=...
  JUDGE_EXTRA='{"reasoning_effort": "low"}'  — додаткові параметри запиту (необов'язково)
  (актуальні ID моделей: https://console.groq.com/docs/models; llama-3.3-70b-versatile вимкнено 16.08.2026)
Neo4j (граф ЛР9):  NEO4J_URI=neo4j://localhost:7687  NEO4J_USER=neo4j  NEO4J_PASSWORD=...  GRAPH_BACKEND=neo4j|csv
"""
import os
from dataclasses import dataclass, field, replace

from common import SENSITIVITY_ORDER

STUB = os.environ.get("LAB11_STUB") == "1"

ROLES = {"external": "public", "analyst": "internal", "dispatcher": "restricted", "admin": "restricted"}


@dataclass
class Settings:

    strategy: str = "hierarchical"
    embed_model: str = "e5-small"
    reranker: str = "mmarco"
    top_k: int = 5                     
    max_source_words: int = 150        
    candidates: int = 30            
    
    gen_provider: str = field(default_factory=lambda: os.environ.get("GEN_PROVIDER", "ollama"))
    gen_base_url: str = field(default_factory=lambda: os.environ.get("GEN_BASE_URL", "http://localhost:11434"))
    gen_model: str = field(default_factory=lambda: os.environ.get("GEN_MODEL", "qwen2.5:7b"))
    gen_api_key: str = field(default_factory=lambda: os.environ.get("GEN_API_KEY", ""))
    gen_num_ctx: int = int(os.environ.get("GEN_NUM_CTX", "8192"))
    max_tokens: int = 400
    temperature: float = 0.0
    seed: int = 42
    prompt_version: str = "rag_v1"
    # вихідний фільтр (додано після аналізу провалів Результату 4):
    #   guard_leak — прибирати речення з службовою міткою / текстом системного промпту (завжди увімкнено);
    #   guard_uncited — відповідь без жодної валідної цитати замінювати на «не знаю» (за замовчуванням вимкнено)
    guard_leak: bool = os.environ.get("GUARD_LEAK", "1") == "1"
    guard_uncited: bool = os.environ.get("GUARD_UNCITED", "0") == "1"
    # суддя
    judge_base_url: str = field(default_factory=lambda: os.environ.get("JUDGE_BASE_URL", ""))
    judge_model: str = field(default_factory=lambda: os.environ.get("JUDGE_MODEL", ""))
    judge_api_key: str = field(default_factory=lambda: os.environ.get("JUDGE_API_KEY", ""))
    judge_extra: str = field(default_factory=lambda: os.environ.get("JUDGE_EXTRA", ""))
    judge_is_external: bool = True    
    # граф
    graph_backend: str = field(default_factory=lambda: os.environ.get("GRAPH_BACKEND", "neo4j"))
    graph_hops: int = 2
    graph_max_facts: int = 25
  
    price_in_per_m: float = float(os.environ.get("PRICE_IN_PER_M", "0"))
    price_out_per_m: float = float(os.environ.get("PRICE_OUT_PER_M", "0"))

    def with_(self, **kw):
        return replace(self, **kw)


def max_sensitivity(role):
    if role not in ROLES:
        raise ValueError(f"невідома роль: {role}")
    return ROLES[role]


def allowed(sensitivity, role):
    return SENSITIVITY_ORDER[sensitivity] <= SENSITIVITY_ORDER[max_sensitivity(role)]
