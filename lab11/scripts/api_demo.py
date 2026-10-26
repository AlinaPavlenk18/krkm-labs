"""Результат 3, демо: ті самі запити до запущеного API від двох ролей (analyst і external) + коди помилок.

Спочатку запустіть сервер (див. README), ключі — у змінних DEMO_KEY_ANALYST, DEMO_KEY_EXTERNAL, DEMO_KEY_DISPATCHER
(ті самі значення, що й у LAB11_API_KEYS). Скрипт друкує роль, джерела з рівнями конфіденційності, відповідь, коди 401/403/422/429.
Запуск: python scripts/api_demo.py [--url http://127.0.0.1:8000]
"""
import argparse
import os
from urllib.parse import quote

import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    a = ap.parse_args()
    keys = {"analyst": os.environ["DEMO_KEY_ANALYST"], "external": os.environ["DEMO_KEY_EXTERNAL"],
            "dispatcher": os.environ.get("DEMO_KEY_DISPATCHER")}
    print("GET /health →", requests.get(a.url + "/health").json())
    q = "Які інциденти зафіксовано в журналі диспетчерської служби в жовтні 2026 року?"
    for role in ("external", "analyst", "dispatcher"):
        if not keys[role]:
            continue
        r = requests.post(a.url + "/ask", json={"question": q, "top_k": 5}, headers={"X-API-Key": keys[role]})
        d = r.json()
        print("=" * 90, f"\nРОЛЬ {role}: HTTP {r.status_code}")
        if r.ok:
            print("джерела:", ", ".join(f"{s['id']} ({s['sensitivity']})" for s in d["sources"]))
            print("відповідь:", d["answer"])
    restricted = "kb15#par000"
    for role in ("analyst", "dispatcher"):
        if keys[role]:
            r = requests.get(f"{a.url}/sources/{quote(restricted, safe='')}", headers={"X-API-Key": keys[role]})
            print(f"GET /sources/{restricted} як {role} → HTTP {r.status_code} {r.json().get('detail', r.json().get('title', ''))}")
    print("без ключа →", requests.post(a.url + "/ask", json={"question": q}).status_code)
    print("хибний ключ →", requests.post(a.url + "/ask", json={"question": q}, headers={"X-API-Key": "bad"}).status_code)
    print("top_k = 50 →", requests.post(a.url + "/ask", json={"question": q, "top_k": 50}, headers={"X-API-Key": keys["analyst"]}).status_code)
    print("неіснуюче джерело →", requests.get(f"{a.url}/sources/{quote('kb00#par999', safe='')}", headers={"X-API-Key": keys["analyst"]}).status_code)


if __name__ == "__main__":
    main()
