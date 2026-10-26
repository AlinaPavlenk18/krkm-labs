"""Результат 3: демонстрація ліміту запитів (429 + Retry-After).

Надсилає N одночасних запитів /ask з одним ключем. Перевірка ліміту виконується до виклику LLM, тому зайві
запити одразу отримують 429, а дозволені чекають на відповідь моделі.
Запуск (сервер запущено з RATE_LIMIT_PER_MIN = 10): python scripts/rate_limit_demo.py --n 12
"""
import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--n", type=int, default=12)
    a = ap.parse_args()
    key = os.environ["DEMO_KEY_EXTERNAL"]
    t0 = time.perf_counter()

    def one(i):
        r = requests.post(a.url + "/ask", json={"question": "Що таке MAPE?", "top_k": 1}, headers={"X-API-Key": key}, timeout=900)
        return i, r.status_code, r.headers.get("Retry-After"), round(time.perf_counter() - t0, 1)
    with ThreadPoolExecutor(a.n) as ex:
        res = sorted(ex.map(one, range(1, a.n + 1)), key=lambda x: x[3])
    for i, code, ra, t in res:
        print(f"запит {i:>2}: HTTP {code}" + (f"  Retry-After: {ra} с" if ra else "") + f"  (через {t} с)")
    print("Разом:", {c: sum(1 for x in res if x[1] == c) for c in sorted({x[1] for x in res})})


if __name__ == "__main__":
    main()
