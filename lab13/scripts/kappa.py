"""Узгодженість двох розмітників (Cohen's κ) на ≥ 30 твердженнях.
Розмітники A (авторка) і B незалежно заповнюють колонки label_A і label_B значенням
з колонки options (тип відношення або NONE), не дивлячись у data/kappa_key.csv і в золотий набір.
"""
import csv, json, random, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.gold_assist import scan  
from src.schema import RELATION_TYPES  

TEXT_DOCS = {"kb02", "kb05", "kb06", "kb11", "kb12", "kb14", "prj10"}   # kb15 (restricted) не показуємо другому розмітнику


def make():
    docs = {json.loads(l)["doc_id"]: json.loads(l)["text"] for l in open(ROOT / "data/docs.jsonl", encoding="utf-8")}
    gold = {}
    for g in map(json.loads, open(ROOT / "data/gold.jsonl", encoding="utf-8")):
        if g["kind"] == "relation":
            for ev in [g["evidence"]] + g.get("alt_evidence", []):
                gold.setdefault((g["doc_id"], g["head"], g["tail"]), []).append((g["type"], ev))
    cands = []
    for did in sorted(TEXT_DOCS):
        for sent in re.split(r"(?<=[.!?])\s+|\n+", docs[did]):
            ents = [(t, c) for (t, c) in scan(sent)]
            for i, (t1, c1) in enumerate(ents):
                for t2, c2 in ents[i + 1:]:
                    opts = [r for r, (h, t) in RELATION_TYPES.items() if (h, t) in ((t1, t2), (t2, t1))]
                    if not opts or c1 == c2:
                        continue
                    
                    key = next((f"{r}({h}→{t})" for h, t in ((c1, c2), (c2, c1)) for r, ev in gold.get((did, h, t), [])
                                if ev in sent or sent.strip() in ev), "NONE")
                    options = []
                    for r in opts:
                        hh, tt = RELATION_TYPES[r]
                        pairs = [(c1, c2)] if (t1, t2) == (hh, tt) else []
                        pairs += [(c2, c1)] if (t2, t1) == (hh, tt) else []
                        options += [f"{r}({h}→{t})" for h, t in pairs]
                    cands.append({"doc_id": did, "sentence": sent.strip(), "entity_1": c1, "entity_2": c2,
                                  "options": " | ".join(options + ["NONE"]), "key": key})
    uniq = {(c["doc_id"], c["entity_1"], c["entity_2"], c["sentence"]): c for c in cands}.values()
    pos = [c for c in uniq if c["key"] != "NONE"]
    neg = [c for c in uniq if c["key"] == "NONE"]
    rnd = random.Random(42)
    pool = rnd.sample(pos, min(24, len(pos))) + rnd.sample(neg, min(16, len(neg)))
    rnd.shuffle(pool)
    with open(ROOT / "data/kappa_pool.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["item", "doc_id", "sentence", "entity_1", "entity_2", "options", "label_A", "label_B"])
        for i, c in enumerate(pool, 1):
            w.writerow([i, c["doc_id"], c["sentence"], c["entity_1"], c["entity_2"], c["options"], "", ""])
    with open(ROOT / "data/kappa_key.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["item", "key"])
        for i, c in enumerate(pool, 1):
            w.writerow([i, c["key"]])
    print(f"кандидатів {len(pos)} позитивних / {len(neg)} негативних → у пулі {len(pool)}")


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n ** 2
    return po, (po - pe) / (1 - pe) if pe < 1 else 1.0


def score():
    rows = list(csv.DictReader(open(ROOT / "data/kappa_pool.csv", encoding="utf-8-sig"), delimiter=";"))
    key = {r["item"]: r["key"] for r in csv.DictReader(open(ROOT / "data/kappa_key.csv", encoding="utf-8-sig"), delimiter=";")}
    rows = [r for r in rows if r["label_A"].strip() and r["label_B"].strip()]
    norm = lambda s: s.strip().replace(" ", "")
    A, B, K = [norm(r["label_A"]) for r in rows], [norm(r["label_B"]) for r in rows], [norm(key[r["item"]]) for r in rows]
    res = {"n": len(rows)}
    for name, x, y in [("A_vs_B", A, B), ("A_vs_gold", A, K), ("B_vs_gold", B, K)]:
        po, k = kappa(x, y)
        res[name] = {"agreement": round(po, 3), "kappa": round(k, 3)}
    res["disagreements_A_B"] = [{"item": r["item"], "A": a, "B": b} for r, a, b in zip(rows, A, B) if a != b]
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results/kappa.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    {"make": make, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
