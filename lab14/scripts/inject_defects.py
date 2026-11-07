"""Р4, крок 4: навмисно вносить 3 дефекти в поточну версію сховища data_after/ (для демонстрації, що CI їх ловить).

  D1 (SHACL SH1)  ПС №5: currentLoad 468 → 650 при номіналі 500 (у трійках і в графі)
  D2 (pytest PY2) зв'язок HAS_METER на неіснуючий лічильник Meter_AMI00000
  D3 (pytest PY4) у kb04 нове твердження «Louvain знайшов 14 спільнот» — третє значення без рішення
Повернення: python quality/fix_store.py (перебудувати data_after) або git revert коміту з дефектами.
"""
import csv
import json
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
A = LAB / "data_after"


def edit_csv(path, fn):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    fields = list(rows[0].keys())
    rows = fn(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def d1(rows):
    for r in rows:
        if r.get("subject") == "Substation_5" and r.get("predicate") == "currentLoad":
            r["object"] = "650.0"
        if r.get("id") == "Substation_5":
            r["currentLoad"] = "650.0"
    return rows


edit_csv(A / "store" / "triples.csv", d1)
edit_csv(A / "store" / "graph" / "nodes_substation.csv", d1)
edit_csv(A / "store" / "graph" / "rels_has_meter.csv",
         lambda rows: rows + [{**rows[0], "start": "Consumer_1002", "end": "Meter_AMI00000"}])
p = A / "corpus" / "docs.jsonl"
docs = [json.loads(x) for x in open(p, encoding="utf-8")]
for d in docs:
    if d["doc_id"] == "kb04":
        d["sections"][-1]["text"] += " За повторним аналізом Louvain знайшов 14 спільнот."
p.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8")
print("Внесено D1 (SH1), D2 (PY2), D3 (PY4) у data_after/")
