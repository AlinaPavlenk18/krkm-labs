"""СР11, крок 3–4: розподіл результатів і причин відмов за перевіреною людиною розміткою.

Вхід: results/sr11_review.csv (human_label, human_cause; порожні клітинки → автоматична оцінка, це позначається).
Вихід: results/sr11_summary.json, docs/sr11_summary.md (таблиці: результат × категорія, розподіл причин,
узгодженість судді з людиною), docs/sr11_causes.png (якщо встановлено matplotlib).
"""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATS = ["simple", "multistep", "noanswer", "conflict", "harmful"]
LABELS = ["правильно", "частково", "ні"]
CAUSES = ["пошук", "контекст", "генерація", "політика"]


def read(path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    first = text.splitlines()[0]
    delim = max([";", ",", "\t"], key=first.count)
    rows = [{k.strip().lstrip("\ufeff"): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(text.splitlines(True), delimiter=delim)]
    for r in rows:                    
        for col in ("human_label", "human_cause", "auto_label", "auto_cause"):
            v = r.get(col, "").strip().lower()
            r[col] = "—" if v in ("-", "–", "—") else v
        v = r.get("human_judge_ok", "").strip().lower()
        r["human_judge_ok"] = {"1": "1", "1.0": "1", "1,0": "1", "так": "1", "0": "0", "0.0": "0", "0,0": "0", "ні": "0"}.get(v, "")
    return rows


def main():
    rows = read(ROOT / "results" / "sr11_review.csv")
    out, auto_used = [], 0
    for r in rows:
        lab = r.get("human_label") or r["auto_label"]
        cause = r.get("human_cause") or r["auto_cause"]
        auto_used += not r.get("human_label")
        out.append({"id": r["id"], "category": r["category"], "label": lab, "cause": "—" if lab == "правильно" else cause,
                    "changed": bool(r.get("human_label")) and (r["human_label"] != r["auto_label"] or (r.get("human_cause") or r["auto_cause"]) != r["auto_cause"])})
    by_cat = {c: Counter(x["label"] for x in out if x["category"] == c) for c in CATS}
    causes = Counter(x["cause"] for x in out if x["label"] != "правильно")
    causes_by_cat = {c: Counter(x["cause"] for x in out if x["category"] == c and x["label"] != "правильно") for c in CATS}
    jr = [r for r in rows if r.get("human_judge_ok") in ("0", "1") and r.get("judge_faithfulness")]
    summ = {"n": len(out), "labels": dict(Counter(x["label"] for x in out)), "by_category": {c: dict(v) for c, v in by_cat.items()},
            "causes": dict(causes), "causes_by_category": {c: dict(v) for c, v in causes_by_cat.items()},
            "auto_labels_used": auto_used, "human_changed": [x["id"] for x in out if x["changed"]],
            "judge_check": {"n": len(jr), "human_agrees": sum(r["human_judge_ok"] == "1" for r in jr),
                            "disagree_ids": [r["id"] for r in jr if r["human_judge_ok"] == "0"]}}
    (ROOT / "results" / "sr11_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    L = ["| Категорія | n | правильно | частково | ні |", "|---|---|---|---|---|"]
    for c in CATS:
        v = by_cat[c]
        L.append(f"| {c} | {sum(v.values())} | {v['правильно']} | {v['частково']} | {v['ні']} |")
    tot = Counter(x["label"] for x in out)
    L += [f"| **разом** | {len(out)} | {tot['правильно']} | {tot['частково']} | {tot['ні']} |", "",
          "| Причина відмови | Кількість | Частка серед відмов |", "|---|---|---|"]
    nf = sum(causes.values())
    for k in CAUSES + [k for k in causes if k not in CAUSES]:
        if causes.get(k):
            L.append(f"| {k} | {causes[k]} | {causes[k] / nf:.0%} |")
    L += ["", f"Перевірка судді людиною: {summ['judge_check']['human_agrees']} з {summ['judge_check']['n']} оцінок підтверджено"
              + (f"; не підтверджено: {', '.join(summ['judge_check']['disagree_ids'])}" if summ['judge_check']['disagree_ids'] else "") + ".",
          f"Автоматичних (неперевірених) оцінок: {auto_used}; змінено людиною: {', '.join(summ['human_changed']) or 'немає'}."]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "sr11_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 3))
        ks = [k for k in CAUSES if causes.get(k)]
        ax.barh(ks, [causes[k] for k in ks], color="#4C72B0")
        ax.set_xlabel("кількість відмов (частково + ні)")
        for i, k in enumerate(ks):
            ax.text(causes[k] + 0.05, i, str(causes[k]), va="center")
        ax.invert_yaxis()
        fig.tight_layout()
        fig.savefig(ROOT / "docs" / "sr11_causes.png", dpi=150)
        print("Графік: docs/sr11_causes.png")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
