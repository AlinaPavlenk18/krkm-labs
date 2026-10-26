"""Результат 5: порівняння двох прогонів run_eval.py (до / після зміни одного керованого фактора).

Друкує й зберігає docs/rag_optimization_table.md: якість (correctness, context recall, faithfulness, citation accuracy,
abstention, conflict, injection), p50 / p95 затримки, токени, вартість — і дельти; плюс список тестів, де змінилася
правильність відповіді.
Запуск: python scripts/compare_runs.py --a baseline --b topk3
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = [
    ("correctness_answerable", "Правильність (answerable, ключові факти)", True),
    ("context_recall", "Context recall (вікно у промпті)", True),
    ("faithfulness", "Faithfulness (суддя)", True),
    ("citation_accuracy", "Точність цитат (суддя)", True),
    ("citation_validity", "Валідність цитат (авто)", True),
    ("abstention_correct_noanswer", "Правильні «не знаю» (noanswer)", True),
    ("false_abstention_answerable", "Хибні «не знаю» (answerable)", False),
    ("conflict_both_versions", "Конфлікт: обидві версії", True),
    ("injection_pass", "Захист від injection", True),
    ("latency_ms_p50", "Затримка p50, мс", False),
    ("latency_ms_p95", "Затримка p95, мс", False),
    ("tokens_prompt_avg", "Токени промпту (сер.)", False),
    ("tokens_completion_avg", "Токени відповіді (сер.)", False),
    ("cost_usd_total", "Вартість прогону, $", False),
]


def load(name):
    d = ROOT / "results" / name
    s = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    recs = {}
    for line in (d / "records.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        recs[r["id"]] = r
    return s, recs


def fmt(v):
    if v is None:
        return "—"
    return f"{v:.3f}" if isinstance(v, float) and abs(v) < 10 else f"{v:,.1f}".replace(",", " ") if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="baseline")
    ap.add_argument("--b", default="topk3")
    a = ap.parse_args()
    sa, ra = load(a.a)
    sb, rb = load(a.b)
    lines = [f"| Метрика | {a.a} (top_k={sa['top_k']}) | {a.b} (top_k={sb['top_k']}) | Δ | Краще? |", "|---|---|---|---|---|"]
    for key, title, higher in METRICS:
        x, y = sa.get(key), sb.get(key)
        if x is None or y is None:
            d, better = None, "—"
        else:
            d = y - x
            better = "=" if abs(d) < 1e-9 else ("так" if (d > 0) == higher else "ні")
        lines.append(f"| {title} | {fmt(x)} | {fmt(y)} | {fmt(d) if d is not None else '—'} | {better} |")
    changed = [(i, ra[i]["auto"].get("correct"), rb[i]["auto"].get("correct")) for i in ra if i in rb
               and ra[i]["auto"].get("correct") != rb[i]["auto"].get("correct")]
    lines += ["", f"Тести, де змінилася правильність ({len(changed)}):", ""]
    lines += [f"- {i}: {x} → {y}" for i, x, y in changed] or ["- немає"]
    if sa.get("latency_ms_p50") and sb.get("latency_ms_p50"):
        lines += ["", f"Зміна p50: {100 * (sb['latency_ms_p50'] / sa['latency_ms_p50'] - 1):+.1f} %; "
                      f"токенів промпту: {100 * (sb['tokens_prompt_avg'] / sa['tokens_prompt_avg'] - 1):+.1f} %."]
    out = ROOT / "docs" / "rag_optimization_table.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
