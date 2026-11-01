"""Оцінювання витягу проти золотого набору: P/R/F1 загалом, за типами й за джерелом документа.

Одиниця порівняння: сутність — (документ, тип, канонічний ID); відношення — (документ, тип, голова, хвіст).
  python -m src.evaluate --split test --runs results/rules_test.jsonl results/llm_test.jsonl
"""
import argparse, json
from collections import defaultdict
from pathlib import Path

from src.schema import DEV_DOCS

ROOT = Path(__file__).resolve().parents[1]


def key(r):
    if r["kind"] == "entity":
        return (r["doc_id"], "E", r["type"], r["canonical"])
    return (r["doc_id"], "R", r["type"], r["head"], r["tail"])


def load(path, split=None):
    out = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    return [r for r in out if split is None or r.get("split", split) == split]


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"P": round(p, 3), "R": round(r, 3), "F1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def group(doc_id):
    return "registers" if doc_id.startswith("gen") else "articles"


def evaluate(gold, pred, docs=None):
    docs = docs or {g["doc_id"] for g in gold}
    G = {key(g) for g in gold if g["doc_id"] in docs}
    P = {key(p) for p in pred if p["doc_id"] in docs}
    res = {}
    buckets = {"ALL": lambda k: True, "ENTITIES": lambda k: k[1] == "E", "RELATIONS": lambda k: k[1] == "R",
               "articles": lambda k: group(k[0]) == "articles", "registers": lambda k: group(k[0]) == "registers",
               "articles·RELATIONS": lambda k: group(k[0]) == "articles" and k[1] == "R",
               "registers·RELATIONS": lambda k: group(k[0]) == "registers" and k[1] == "R"}
    for t in sorted({k[2] for k in G | P}):
        buckets[t] = (lambda tt: lambda k: k[2] == tt)(t)
    for name, f in buckets.items():
        g, p = {k for k in G if f(k)}, {k for k in P if f(k)}
        res[name] = prf(len(g & p), len(p - g), len(g - p))
    errors = {"fp": sorted(P - G), "fn": sorted(G - P)}
    return res, errors


def table(res, title):
    lines = [f"### {title}", "", "| Зріз | P | R | F1 | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
    for k, v in res.items():
        lines.append(f"| {k} | {v['P']:.3f} | {v['R']:.3f} | {v['F1']:.3f} | {v['tp']} | {v['fp']} | {v['fn']} |")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--runs", nargs="+", required=True)
    a = ap.parse_args()
    gold = [g for g in load(ROOT / "data/gold.jsonl") if g["split"] == a.split]
    alldocs = [json.loads(l)["doc_id"] for l in open(ROOT / "data/docs.jsonl", encoding="utf-8")]
    docs = {d for d in alldocs if (d in DEV_DOCS) == (a.split == "dev")}
    for run in a.runs:
        pred = load(run)
        res, err = evaluate(gold, pred, docs)
        print(table(res, f"{Path(run).name} · {a.split}"))
        print(f"FP приклади: {err['fp'][:8]}\nFN приклади: {err['fn'][:8]}\n")
