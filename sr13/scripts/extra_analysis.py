"""Додатковий аналіз (після evaluate.py; без налаштування методів):
  1) гібриди без параметрів: правила ∪ LLM, правила ∪ spaCy;
  2) бутстреп за реченнями (2000 вибірок, seed 42): 95 % ДІ різниці F1 між методами;
  3) чутливість до розмітки: варіант data/gold_variant_guide.csv, де 2 речення (s06, s27) розмічено строго
     за docs/annotation_guide.md. Основна розмітка — data/gold.csv.
"""
import json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common import gold, load, sentences  


def score(G, P, ids):
    tp = sum(len(P[i] & G[i]) for i in ids); fp = sum(len(P[i] - G[i]) for i in ids); fn = sum(len(G[i] - P[i]) for i in ids)
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    return {"P": round(p, 3), "R": round(r, 3), "F1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "TP": tp, "FP": fp, "FN": fn}


def main():
    G, V = gold(), gold("data/gold_variant_guide.csv")
    P = {m: load(m) for m in ("rules", "spacy", "llm")}
    P["rules+llm"] = {i: P["rules"][i] | P["llm"][i] for i in G}
    P["rules+spacy"] = {i: P["rules"][i] | P["spacy"][i] for i in G}
    ids = list(G)
    S = {s["id"]: s for s in sentences()}
    out = {"main_gold": {m: score(G, P[m], ids) for m in P},
           "variant_gold_guide": {m: score(V, P[m], ids) for m in P},
           "by_lr13_dev_doc": {d: {m: score(G, P[m], [i for i in ids if S[i]["lr13_dev_doc"] == d]) for m in ("rules", "spacy", "llm")}
                               for d in ("1", "0")}}
    rnd, pairs = random.Random(42), [("llm", "rules"), ("llm", "spacy"), ("rules", "spacy"), ("rules+llm", "llm"), ("rules+llm", "rules")]
    diffs = {p: [] for p in pairs}
    for _ in range(2000):
        b = [rnd.choice(ids) for _ in ids]
        for a, c in pairs:
            diffs[(a, c)].append(score(G, P[a], b)["F1"] - score(G, P[c], b)["F1"])
    out["bootstrap_F1_diff"] = {f"{a} - {c}": {"ci95": [round(sorted(v)[50], 3), round(sorted(v)[1949], 3)],
                                               "share_gt_0": round(sum(x > 0 for x in v) / len(v), 3)} for (a, c), v in diffs.items()}
    (ROOT / "results/extra.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for k in ("main_gold", "variant_gold_guide"):
        print(k, {m: v["F1"] for m, v in out[k].items()})
    for k, v in out["bootstrap_F1_diff"].items():
        print(f"{k:18} 95 % ДІ {v['ci95']}  частка > 0: {v['share_gt_0']}")


if __name__ == "__main__":
    main()
