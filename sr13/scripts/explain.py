"""LLM пояснює сумнівні відношення. Розмітку це НЕ змінює — рішення приймає людина.

Сумнівні = трійки, щодо яких три методи не одностайні (хоч один знайшов, хоч один — ні) або що розходяться з
золотою розміткою. До 20 штук, пріоритет — розбіжності з розміткою.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common import sentences, gold, load  
from src.m3_llm import OLLAMA, MODEL, OPTIONS  
import requests  

SCHEMA = {"type": "object", "required": ["verdict", "explanation"], "properties": {
    "verdict": {"type": "string", "enum": ["так", "ні", "неоднозначно"]}, "explanation": {"type": "string"}}}
SYSTEM = ("Ти — експерт з електромереж. Тобі дають речення і відношення (s, p, o) зі схеми бази знань. "
          "Скажи, чи це відношення ПРЯМО стверджене в реченні (так / ні / неоднозначно), і поясни в 1–2 реченнях, "
          "посилаючись на слова речення. Предикати: FEEDS — пряме живлення підстанції; LOCATED_IN — область "
          "підстанції; MANAGES — постійна відповідальність диспетчера; CONNECTED_TO — підключення споживача; "
          "HAS_METER — лічильник споживача; FORECASTS_FOR — модель прогнозує для підстанції; INSTANCE_OF — тип моделі.")


def main():
    S, G = {s["id"]: s["text"] for s in sentences()}, gold()
    P = {m: load(m) for m in ("rules", "spacy", "llm")}
    items = []
    for sid in S:
        union = set().union(*(P[m].get(sid, set()) for m in P)) | G[sid]
        for t in sorted(union):
            found = [m for m in P if t in P[m].get(sid, set())]
            in_gold = t in G[sid]
            if len(found) in (1, 2) or (found and not in_gold) or (in_gold and not found):
                prio = 0 if (t in P["llm"].get(sid, set())) != in_gold else 1
                items.append((prio, sid, t, found, in_gold))
    items = sorted(items, key=lambda x: (x[0], x[1]))[:20]
    out = []
    for _, sid, t, found, in_gold in items:
        user = f"Речення: «{S[sid]}»\nВідношення: {t[0]} {t[1]} {t[2]}"
        r = requests.post(f"{OLLAMA}/api/chat", timeout=600, json={
            "model": MODEL, "stream": False, "format": SCHEMA, "options": OPTIONS,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]})
        r.raise_for_status()
        ans = json.loads(r.json()["message"]["content"])
        rec = {"id": sid, "triple": t, "found_by": found, "in_gold": in_gold, "model": MODEL, "options": OPTIONS,
               "verdict": ans.get("verdict"), "explanation": ans.get("explanation"), "human_decision": ""}
        out.append(rec)
        print(f"{sid} {' '.join(t)} | знайшли: {found or '—'} | у розмітці: {in_gold} | LLM: {rec['verdict']}", flush=True)
    with open(ROOT / "llm_log/explanations.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    md = ["# Пояснення LLM щодо сумнівних відношень (сирий вихід; рішення — людини)", "",
          "| Речення | Трійка | Знайшли методи | У розмітці | Вердикт LLM | Пояснення LLM |", "|---|---|---|---|---|---|"]
    for r in out:
        md.append(f"| {r['id']} | {' '.join(r['triple'])} | {', '.join(r['found_by']) or '—'} | {'так' if r['in_gold'] else 'ні'} | "
                  f"{r['verdict']} | {r['explanation'].replace('|', '/')} |")
    (ROOT / "docs/explanations_auto.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
