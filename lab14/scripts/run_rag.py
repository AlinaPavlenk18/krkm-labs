"""Р5. Повторний прогін тестового набору RAG ЛР11 на іншій версії корпусу — без змін коду ЛР11.

Код RAG (пошук, генератор, суддя, метрики) береться з ../lab11 як є; підмінюються лише шлях до корпусу і папка
результатів. Налаштування — як у baseline ЛР11: top_k = 5, rag_v1, qwen2.5:7b, temperature 0, seed 42, суддя з
JUDGE_* (той самий, що в ЛР11). Вихідний фільтр GUARD_* вимкнено, бо в baseline ЛР11 його ще не було —
так різниця «до/після» пояснюється лише даними.

  . .\\set_env.ps1                                  # JUDGE_API_KEY тощо (як у ЛР11; файл не в git)
  python scripts/run_rag.py --version after         # корпус data_after → results/rag_after/
  python scripts/run_rag.py --version baseline      # (необов'язково, контроль) корпус data → results/rag_baseline_rerun/
  python scripts/run_rag.py --version after --rejudge   # переоцінити суддею збережені відповіді
Тривалість: ≈ 39 запитів × 2–3 хв на CPU (baseline ЛР11: p50 157 с). Можна перервати й запустити знову — див. --limit.
"""
import argparse
import os
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
LAB11 = LAB.parent / "lab11"

os.environ.setdefault("GUARD_LEAK", "0")
os.environ.setdefault("GUARD_UNCITED", "0")
sys.path.insert(0, str(LAB11 / "src"))
sys.path.insert(0, str(LAB11 / "scripts"))

import common as c11  
import run_eval 

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["after", "baseline"], required=True)
    ap.add_argument("--rejudge", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    base = LAB / ("data_after" if a.version == "after" else "data")
    c11.CLEAN = base / "corpus"                                    # Retriever читає CLEAN / "docs.jsonl"
    run_eval.RESULTS = LAB / "results"
    name = "rag_after" if a.version == "after" else "rag_baseline_rerun"
    print(f"Корпус: {c11.CLEAN / 'docs.jsonl'}; GUARD_LEAK={os.environ['GUARD_LEAK']}; результати: results/{name}/")
    run_eval.run(argparse.Namespace(name=name, set=None, no_judge=a.no_judge, rejudge=a.rejudge, limit=a.limit))
