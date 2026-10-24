"""Запускає СР10 повністю: запити -> експеримент -> аналіз розбіжностей. Додатково пише results/environment.json.

  python scripts/run_all.py — 5 моделей (≈ 4 ГБ завантажень за першого запуску);
  python scripts/run_all.py --models e5-small e5-base ml-minilm en-minilm   — без bge-m3 (≈ 1,8 ГБ).
"""
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
extra = sys.argv[1:]
times = {}
for name, args in [("queries", ["scripts/build_queries.py"]), ("experiment", ["scripts/run_experiment.py"] + extra),
                   ("disagreements", ["scripts/analyze_disagreements.py"])]:
    print(f"\n=== {name}", flush=True)
    t = time.perf_counter()
    if subprocess.run([sys.executable] + args, cwd=ROOT).returncode:
        sys.exit(f"Крок {name} завершився з помилкою — надішліть вивід вище.")
    times[name] = round(time.perf_counter() - t, 1)
env = {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor()}
for mod in ["torch", "sentence_transformers", "transformers", "faiss", "numpy"]:
    try:
        env[mod] = __import__(mod).__version__
    except Exception:
        env[mod] = None
(ROOT / "results" / "environment.json").write_text(json.dumps({"env": env, "step_seconds": times}, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nГотово:", times, "\nНадішліть results/sr10_results.json, results/environment.json, docs/sr10_tables.md, docs/disagreements.md і eval/variants_review.csv.")
