"""LLM пропонує зіркову схему (qwen2.5:7b в Ollama, локально, t = 0, seed 42).
Сирий вихід → llm_log/qwen_schema_raw.md. Людина знаходить у ньому недоліки (docs/llm_review.md).
"""
import json, os, time
from datetime import datetime
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.getenv("SCHEMA_MODEL", "qwen2.5:7b")
prompt = (ROOT / "prompts/schema_v1.md").read_text(encoding="utf-8")
t0 = time.time()
r = requests.post(os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/chat", timeout=1200, json={
    "model": MODEL, "stream": False,
    "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 2000},
    "messages": [{"role": "user", "content": prompt}]})
r.raise_for_status()
j = r.json()
out = (f"# Сирий вихід LLM (СР12)\n\n- дата: {datetime.now().isoformat(timespec='seconds')}\n- модель: {MODEL}\n"
       f"- параметри: temperature 0, seed 42, num_ctx 8192, num_predict 2000\n- підказка: prompts/schema_v1.md\n"
       f"- токени: {j.get('prompt_eval_count')} вхід / {j.get('eval_count')} вихід; час {time.time() - t0:.1f} с\n\n"
       f"---\n\n{j['message']['content']}\n")
(ROOT / "llm_log/qwen_schema_raw.md").write_text(out, encoding="utf-8")
print(out)
