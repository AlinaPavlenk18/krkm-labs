"""Крок 3: P/R/F1 і вартість трьох методів на однаковій розмітці (data/gold.csv) + файл помилок."""
import argparse, csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common import sentences, gold, load, PREDICATES 

METHODS = [("rules", "1 · правила"), ("spacy", "2 · spaCy-модель"), ("llm", "3 · LLM зі схемою")]


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"P": round(p, 3), "R": round(r, 3), "F1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "TP": tp, "FP": fp, "FN": fn}


def classify(t, other, kind):
    s, p, o = t
    if (o, p, s) in other:
        return "напрям"
    if any(x[0] == s and x[2] == o and x[1] != p for x in other):
        return "хибний предикат"
    return "хибне відношення (вигадане/зайва пара)" if kind == "FP" else "пропуск"


def main(gold_path, tag):
    G, S = gold(gold_path), {s["id"]: s for s in sentences()}
    res, errs = {"_gold": {"sentences": len(G), "triples": sum(map(len, G.values())),
                           "by_predicate": dict(Counter(t[1] for v in G.values() for t in v))}}, []
    md = [f"# Порівняння методів витягу відношень на 50 реченнях ({gold_path})", "",
          f"Золотих трійок: {res['_gold']['triples']} у {sum(1 for v in G.values() if v)} реченнях; "
          f"речень без відношень: {sum(1 for v in G.values() if not v)}.", ""]
    for m, name in METHODS:
        try:
            P = load(m)
        except FileNotFoundError:
            print(f"немає results/{m}.jsonl — пропускаю"); continue
        meta = json.loads((ROOT / f"results/{m}_meta.json").read_text(encoding="utf-8"))
        cnt = Counter()
        exact = 0
        for sid, g in G.items():
            p = P.get(sid, set())
            exact += p == g
            for t in p & g:
                for k in ("ALL", t[1], S[sid]["group"], f"lr13dev={S[sid]['lr13_dev_doc']}"):
                    cnt[(k, "TP")] += 1
            for t in p - g:
                for k in ("ALL", t[1], S[sid]["group"], f"lr13dev={S[sid]['lr13_dev_doc']}"):
                    cnt[(k, "FP")] += 1
                errs.append({"method": m, "id": sid, "error": "FP", "class_hint": classify(t, g, "FP"),
                             "s": t[0], "p": t[1], "o": t[2], "text": S[sid]["text"]})
            for t in g - p:
                for k in ("ALL", t[1], S[sid]["group"], f"lr13dev={S[sid]['lr13_dev_doc']}"):
                    cnt[(k, "FN")] += 1
                errs.append({"method": m, "id": sid, "error": "FN", "class_hint": classify(t, p, "FN"),
                             "s": t[0], "p": t[1], "o": t[2], "text": S[sid]["text"]})
        keys = ["ALL", "article", "register", "lr13dev=1", "lr13dev=0"] + PREDICATES
        res[m] = {k: prf(cnt[(k, "TP")], cnt[(k, "FP")], cnt[(k, "FN")]) for k in keys}
        res[m]["_exact_sentences"] = exact
        res[m]["_meta"] = meta
        md += [f"## {name}", "", f"Речень, розмічених повністю правильно: {exact} з {len(G)}; "
               f"час {meta['seconds_per_sentence']} с/речення (+ завантаження {meta.get('load_seconds', 0)} с); "
               f"токенів/речення: {meta.get('tokens_per_sentence', 0)}; вартість {meta['cost_uah']} грн.", "",
               "| Зріз | P | R | F1 | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
        for k in keys:
            v = res[m][k]
            if v["TP"] + v["FP"] + v["FN"]:
                md.append(f"| {k} | {v['P']:.3f} | {v['R']:.3f} | {v['F1']:.3f} | {v['TP']} | {v['FP']} | {v['FN']} |")
        md.append("")
    suf = f"_{tag}" if tag else ""
    (ROOT / f"results/eval{suf}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(ROOT / f"results/errors{suf}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["method", "id", "error", "class_hint", "s", "p", "o", "text"], delimiter=";")
        w.writeheader(); w.writerows(errs)
    (ROOT / f"docs/results_auto{suf}.md").write_text("\n".join(md), encoding="utf-8")
    for m, name in METHODS:
        if m in res:
            a = res[m]["ALL"]
            print(f"{name:18} P {a['P']:.3f}  R {a['R']:.3f}  F1 {a['F1']:.3f}  (TP {a['TP']}, FP {a['FP']}, FN {a['FN']}) | "
                  f"точних речень {res[m]['_exact_sentences']}/50 | {res[m]['_meta']['seconds_per_sentence']} с/реч.")
    print(f"помилок: {len(errs)} → results/errors{suf}.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="data/gold.csv")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    main(a.gold, a.tag)
