"""Результат 4, крок 4 (план виправлення): ефект вихідного фільтра на вже отриманих відповідях.

Фільтр (src/rag.py: output_guard) — детермінована постобробка тексту відповіді, тому його ефект можна виміряти
на збережених відповідях генератора (results/<run>/records.jsonl) без повторного запуску LLM: відповіді ті самі,
змінюється лише те, що отримує користувач. Варіанти: none (як було), leak (вилучення мітки / системного тексту),
leak+uncited (додатково: відповідь без валідних цитат → «не знаю»).
Вихід: docs/guard_effect_table.md.  Запуск: python scripts/guard_offline.py --runs baseline topk3
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from common import EVAL, read_jsonl 
from rag import CANARY, check_citations, is_abstention, load_prompt, output_guard  
from run_eval import auto_metrics, mean  


class _NoRetriever:
    def get(self, cid):
        return None


VARIANTS = {"none": (False, False), "leak": (True, False), "leak+uncited": (True, True)}


def evaluate(run, tests):
    system = load_prompt("rag_v1")[0].replace("{canary}", CANARY)
    rows = read_jsonl(ROOT / "results" / run / "records.jsonl")
    out = {}
    for name, (leak, unc) in VARIANTS.items():
        res = []
        for r in rows:
            t = tests[r["id"]]
            ids = {x["id"] for x in r["sources_full"]}
            text, flags = output_guard(r["answer"], system, ids, leak=leak, uncited=unc)
            cited, invalid, _ = check_citations(text, ids)
            rec = {"_sources_full": r["sources_full"], "answer": text, "citations": cited, "invalid_citations": invalid,
                   "abstained": is_abstention(text), "canary_leak": CANARY in text}
            m = auto_metrics(t, rec, _NoRetriever())
            res.append((t, m, flags, text))
        cat = lambda c: [m for t, m, _, _ in res if t["category"] == c]  # noqa: E731
        out[name] = {
            "correctness_answerable": mean([m["correct"] for m in cat("answerable")]),
            "false_abstention_answerable": mean([m["false_abstain"] for m in cat("answerable")]),
            "abstention_correct_noanswer": mean([m["correct"] for m in cat("noanswer")]),
            "conflict_both_versions": mean([m["correct"] for m in cat("conflict")]),
            "injection_pass": mean([m["correct"] for m in cat("injection")]),
            "canary_leaks": sum(1 for _, m, _, txt in res if CANARY in txt),
            "triggered": {t["id"]: f for t, _, f, _ in res if f},
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["baseline", "topk3"])
    a = ap.parse_args()
    tests = {t["id"]: t for t in read_jsonl(EVAL / "rag_eval.jsonl")}
    lines = []
    for run in a.runs:
        res = evaluate(run, tests)
        lines += [f"### {run}", "", "| Метрика | без фільтра | leak | leak + uncited |", "|---|---|---|---|"]
        for k, title in [("correctness_answerable", "Правильність (answerable)"), ("false_abstention_answerable", "Хибні «не знаю»"),
                         ("abstention_correct_noanswer", "Правильні «не знаю» (noanswer)"), ("conflict_both_versions", "Конфлікт: обидві версії"),
                         ("injection_pass", "Захист від injection"), ("canary_leaks", "Витоків мітки")]:
            lines.append(f"| {title} | " + " | ".join(str(res[v][k]) for v in VARIANTS) + " |")
        lines += ["", "Спрацювання: " + "; ".join(f"{v}: {res[v]['triggered']}" for v in VARIANTS if v != "none"), ""]
    (ROOT / "docs" / "guard_effect_table.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
