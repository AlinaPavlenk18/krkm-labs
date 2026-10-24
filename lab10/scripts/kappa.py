"""Результат 5, крок 2: узгодженість двох розмітників (Cohen's κ).

  python scripts/kappa.py make   — створює аркуш eval/kappa_pool.csv: 12 запитів × топ-6 фрагментів BM25
                                   (структурні фрагменти corpus.jsonl) = 72 пари «запит — фрагмент».
                                   Розмітники A і B НЕЗАЛЕЖНО ставлять 1 (фрагмент містить відповідь повністю
                                   або частково) або 0 у колонки label_A / label_B. Чернетка LLM (за доказами
                                   gold) пишеться окремо в eval/kappa_llm_labels.csv, щоб не підказувати.
  python scripts/kappa.py score  — рахує κ(A, B), а також κ(A, LLM) і κ(B, LLM); пише results/kappa.json.

κ = (p_o − p_e) / (1 − p_e), де p_o — частка збігів, p_e — очікувана частка випадкових збігів
за маргінальними частотами кожного розмітника (Cohen, 1960).
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import DATA, EVAL, RESULTS, read_jsonl, tokenize, write_json  # noqa: E402
from metrics import covers  # noqa: E402

KAPPA_QUERIES = ["q02", "q06", "q09", "q12", "q16", "q19", "q22", "q25", "q27", "q33", "q37", "q43"]
TOP = 6


def make():
    from rank_bm25 import BM25Okapi
    corpus = read_jsonl(DATA / "corpus.jsonl")
    gold = {g["qid"]: g for g in read_jsonl(EVAL / "gold.jsonl")}
    bm = BM25Okapi([tokenize(f"{c['title']}. {c['section']}. {c['text']}") for c in corpus])
    pool, llm = [], []
    for qid in KAPPA_QUERIES:
        g = gold[qid]
        sc = bm.get_scores(tokenize(g["query"]))
        for rank, i in enumerate(sorted(range(len(corpus)), key=lambda j: -sc[j])[:TOP], 1):
            c = corpus[i]
            pid = f"{qid}-{rank}"
            pool.append([pid, qid, g["query"], c["chunk_id"], c["title"], c["section"], c["text"], "", ""])
            llm.append([pid, int(any(covers(c["text"], c["doc_id"], e) for e in g["relevant"]))])
    p = EVAL / "kappa_pool.csv"
    if p.exists():
        print(f"{p} вже існує — не перезаписую (видаліть вручну, якщо треба створити заново)")
    else:
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pair_id", "qid", "query", "chunk_id", "title", "section", "text", "label_A", "label_B"])
            w.writerows(pool)
    with open(EVAL / "kappa_llm_labels.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair_id", "label_llm"])
        w.writerows(llm)
    print(f"пар: {len(pool)} ({len(KAPPA_QUERIES)} запитів × {TOP}); чернетка LLM: {sum(x[1] for x in llm)} релевантних")


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    k = (po - pe) / (1 - pe) if pe < 1 else 1.0
    table = {"11": sum(x == 1 and y == 1 for x, y in zip(a, b)), "10": sum(x == 1 and y == 0 for x, y in zip(a, b)),
             "01": sum(x == 0 and y == 1 for x, y in zip(a, b)), "00": sum(x == 0 and y == 0 for x, y in zip(a, b))}
    return {"n": n, "p_o": round(po, 4), "p_e": round(pe, 4), "kappa": round(k, 4), "table": table}


def interpret(k):
    # шкала Landis & Koch (1977)
    for thr, name in [(0.8, "майже повна"), (0.6, "суттєва"), (0.4, "помірна"), (0.2, "слабка"), (0.0, "незначна")]:
        if k > thr:
            return name
    return "відсутня"


def score():
    with open(EVAL / "kappa_pool.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    with open(EVAL / "kappa_llm_labels.csv", encoding="utf-8-sig") as f:
        llm = {r["pair_id"]: int(r["label_llm"]) for r in csv.DictReader(f)}
    full = [r for r in rows if r["label_A"].strip() in "01" and r["label_A"].strip() and r["label_B"].strip() in "01" and r["label_B"].strip()]
    if len(full) < len(rows):
        print(f"увага: розмічено обома лише {len(full)} з {len(rows)} пар")
    a = [int(r["label_A"]) for r in full]
    b = [int(r["label_B"]) for r in full]
    l = [llm[r["pair_id"]] for r in full]
    out = {"queries": sorted({r["qid"] for r in full}), "pairs": len(full),
           "A_vs_B": kappa(a, b), "A_vs_LLM": kappa(a, l), "B_vs_LLM": kappa(b, l),
           "disagreements_A_B": [{"pair_id": r["pair_id"], "query": r["query"], "chunk_id": r["chunk_id"],
                                  "A": r["label_A"], "B": r["label_B"]} for r in full if r["label_A"] != r["label_B"]]}
    for k in ["A_vs_B", "A_vs_LLM", "B_vs_LLM"]:
        out[k]["interpretation"] = interpret(out[k]["kappa"])
    write_json(RESULTS / "kappa.json", out)
    for k in ["A_vs_B", "A_vs_LLM", "B_vs_LLM"]:
        print(f"{k:9s} κ = {out[k]['kappa']:.3f} ({out[k]['interpretation']}), збіг {out[k]['p_o']:.1%}, таблиця {out[k]['table']}")


if __name__ == "__main__":
    {"make": make, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
