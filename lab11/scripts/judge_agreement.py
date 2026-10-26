"""Результат 4, крок 3: узгодженість судді з людиною.

Вхід — CSV із твердженнями, оціненими суддею, і ручними оцінками людини (1 / 0):
  human_supported — твердження випливає з наданих джерел (порівнюється з judge_supported → faithfulness);
  human_cited_ok  — процитоване джерело підтверджує твердження (порівнюється з judge_cited_ok → citation accuracy).
Для кожного виміру: кількість розмічених, частка збігів, Cohen's κ, матриця 2×2, розбіжності.
Примітка: якщо суддя в розміченій вибірці ставить лише одну оцінку (усі 1), κ = 0 за будь-якої частки збігів
(«парадокс каппи»), тому вибірка має містити й твердження, які суддя оцінив як 0.
Запуск: python scripts/judge_agreement.py --file results/judge_review_v2.csv
        python scripts/judge_agreement.py --name baseline        (старий формат results/<name>/judge_review.csv)
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else None


def read_csv(path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    first = text.splitlines()[0]
    delim = max([";", ",", "\t"], key=first.count)      
    rows = list(csv.DictReader(text.splitlines(True), delimiter=delim))
    rows = [{(k or "").strip().lstrip("\ufeff"): (v or "").strip() if isinstance(v, str) else v for k, v in r.items()} for r in rows]
    for r in rows:                                        
        for col in ("human_supported", "human_cited_ok", "judge_supported", "judge_cited_ok"):
            v = str(r.get(col) or "").strip().lower()
            r[col] = {"1": "1", "1.0": "1", "1,0": "1", "так": "1", "true": "1", "0": "0", "0.0": "0", "0,0": "0", "ні": "0", "false": "0"}.get(v, v)
    print(f"[діагностика] розділювач {delim!r}, рядків {len(rows)}, стовпці: {list(rows[0].keys()) if rows else []}")
    for col in ("human_supported", "human_cited_ok"):
        print(f"[діагностика] заповнено {col}: {sum(1 for r in rows if r.get(col) in ('0', '1'))}")
    return rows


def dim(rows, jcol, hcol):
    rs = [r for r in rows if r.get(hcol) in ("0", "1") and r.get(jcol) in ("0", "1")]
    if not rs:
        return None
    j = [int(r[jcol]) for r in rs]
    h = [int(r[hcol]) for r in rs]
    k = kappa(j, h)
    return {"n": len(rs), "agreement": round(sum(p == q for p, q in zip(j, h)) / len(rs), 3),
            "kappa": round(k, 3) if k is not None else None,
            "confusion": {f"judge{x}_human{y}": sum(1 for p, q in zip(j, h) if p == x and q == y) for x in (1, 0) for y in (1, 0)},
            "disagreements": [{"test_id": r["test_id"], "run": r.get("run", ""), "claim": r["claim"], "judge": r[jcol], "human": r[hcol],
                               "comment": r.get("human_comment", "")} for r in rs if r[jcol] != r[hcol]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--name", default="baseline")
    a = ap.parse_args()
    path = Path(a.file) if a.file else ROOT / "results" / a.name / "judge_review.csv"
    rows = read_csv(path)
    res = {"file": str(path.name), "supported": dim(rows, "judge_supported", "human_supported")}
    if rows and "human_cited_ok" in rows[0]:
        res["cited_ok"] = dim(rows, "judge_cited_ok", "human_cited_ok")
    out = path.with_name(path.stem.replace("judge_review", "judge_agreement") + ".json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    for d in ("supported", "cited_ok"):
        if res.get(d) and res[d]["n"] < 10:
            print(f"[{d}] розмічено лише {res[d]['n']} тверджень; потрібно щонайменше 10")


if __name__ == "__main__":
    main()
