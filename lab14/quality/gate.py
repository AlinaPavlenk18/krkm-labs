"""Р4. Gate якості: запускає всі перевірки checks.py, пише звіт і тренд; код виходу 1 = є блокувальні порушення.

  python quality/gate.py                       # поточна версія сховища (data_after/, якщо є, інакше data/)
  python quality/gate.py --version baseline    # baseline-знімок data/
  python quality/gate.py --record --name after # + рядок у quality/reports/trend.csv і графік тренду
Звіт: quality/reports/check_report.md (таблиця правил і порушень), check_report.json; у CI — також у summary.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from common import DATA, LAB, QUALITY, git_commit
from checks import CHECKS, Ctx, run_all

REPORTS = QUALITY / "reports"
TREND = REPORTS / "trend.csv"


def paths(version):
    base = LAB / ("data_after" if version == "after" else "data")
    return base / "store", base / "corpus" / "docs.jsonl"


def write_report(res, meta):
    REPORTS.mkdir(parents=True, exist_ok=True)
    tools = sorted({r["tool"] for r in res})
    tot = {k: sum(r[k] for r in res) for k in ("violations", "waived", "blocking")}
    by_tool = ", ".join(f"{t}: {sum(r['tool'] == t for r in res)}" for t in tools)
    L = [f"# Звіт перевірок якості — {meta['name']}", "",
         f"Сховище: `{meta['store']}` · корпус: `{meta['corpus']}` · git {meta['commit'] or '—'} · {meta['ts']}", "",
         f"Перевірок: **{len(res)}** ({by_tool}); "
         f"порушень: **{tot['violations']}**, з них за винятками (waivers): {tot['waived']}, блокувальних: **{tot['blocking']}**. "
         f"Результат gate: **{'FAIL — зміни заблоковано' if tot['blocking'] else 'PASS'}**.", "",
         "| ID | Інструмент | Правило | Порушень | Виняток | Статус |", "|---|---|---|---|---|---|"]
    for r in res:
        L.append(f"| {r['id']} | {r['tool']} | {r['title']} | {r['violations']} | {r['waived']} | "
                 f"{ {'PASS': '✅ PASS', 'WAIVED': '⚠️ WAIVED', 'FAIL': '❌ FAIL'}[r['status']] } |")
    L += ["", "## Порушення", ""]
    for r in res:
        if r["details"]:
            L.append(f"**{r['id']}** ({r['title']}):")
            L += [f"- {d}" for d in r["details"][:15]] + ([f"- … ще {len(r['details']) - 15}"] if len(r["details"]) > 15 else [])
            L.append("")
    (REPORTS / "check_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (REPORTS / "check_report.json").write_text(json.dumps({"meta": meta, "results": res}, ensure_ascii=False, indent=2), encoding="utf-8")
    return "\n".join(L)


def record(res, meta):
    new = not TREND.exists()
    with open(TREND, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "name", "commit", "checks", "violations", "waived", "blocking", "failed_checks"])
        w.writerow([meta["ts"], meta["name"], meta["commit"], len(res), sum(r["violations"] for r in res),
                    sum(r["waived"] for r in res), sum(r["blocking"] for r in res),
                    " ".join(r["id"] for r in res if r["status"] == "FAIL")])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = list(csv.DictReader(open(TREND, encoding="utf-8")))
    x = range(len(rows))
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=150)
    ax.plot(x, [int(r["violations"]) for r in rows], marker="o", label="усі порушення")
    ax.plot(x, [int(r["blocking"]) for r in rows], marker="s", label="блокувальні")
    ax.set_xticks(list(x), [r["name"] for r in rows], fontsize=8, rotation=20)
    for i, r in enumerate(rows):
        ax.annotate(r["blocking"], (i, int(r["blocking"])), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7)
    ax.set_ylabel("кількість")
    ax.set_title("Тренд перевірок якості (gate)", fontsize=10)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(REPORTS / "trend.png")
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["baseline", "after"], default="after" if (LAB / "data_after").exists() else "baseline")
    ap.add_argument("--name", default=None)
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--ref-date", default=None)
    a = ap.parse_args()
    store, corpus = paths(a.version)
    meta = {"name": a.name or a.version, "store": str(store.relative_to(LAB)), "corpus": str(corpus.relative_to(LAB)),
            "commit": git_commit(), "ts": datetime.now().isoformat(timespec="seconds")}
    res = run_all(Ctx(store, corpus, ref_date=a.ref_date))
    for r in res:
        print(f"{r['id']:<7} {r['tool']:<11} {r['status']:<6} порушень {r['violations']:>3} (виняток {r['waived']})  {r['title']}")
    md = write_report(res, meta)
    if a.record:
        record(res, meta)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md + "\n")
    blocking = sum(r["blocking"] for r in res)
    print(f"\nGATE: {'FAIL' if blocking else 'PASS'} — блокувальних порушень {blocking}; звіт quality/reports/check_report.md")
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
