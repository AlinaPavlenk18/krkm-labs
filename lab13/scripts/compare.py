import argparse, csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluate import evaluate, load, key, table  
from src.schema import DEV_DOCS  


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    split = ap.parse_args().split
    gold = [g for g in load(ROOT / "data/gold.jsonl") if g["split"] == split]
    docs = {json.loads(l)["doc_id"] for l in open(ROOT / "data/docs.jsonl", encoding="utf-8")}
    docs = {d for d in docs if (d in DEV_DOCS) == (split == "dev")}
    runs = {"A · правила": load(ROOT / f"results/rules_{split}.jsonl")}
    if (ROOT / f"results/llm_{split}.jsonl").exists():
        llm = load(ROOT / f"results/llm_{split}.jsonl")
        runs["Б · LLM"] = llm
        rel_keys = {key(r) for r in runs["A · правила"] if r["kind"] == "relation"}
        runs["Гібрид А+Б"] = [r for r in runs["A · правила"]] + [r for r in llm if r["kind"] == "relation" and key(r) not in rel_keys]
    res, md = {}, [f"# Порівняння методів витягу ({split})", ""]
    rows = []
    for name, pred in runs.items():
        r, err = evaluate(gold, pred, docs)
        res[name] = r
        md += [table(r, name), ""]
        for kind in ("fp", "fn"):
            for k in err[kind]:
                rows.append([name, kind, *k])
    meta = {}
    for m in ("rules", "llm"):
        p = ROOT / f"results/{m}_{split}_meta.json"
        if p.exists():
            meta[m] = json.loads(p.read_text(encoding="utf-8"))
    res["_meta"] = {k: {kk: v for kk, v in vv.items() if kk != "per_doc"} for k, vv in meta.items()}
    (ROOT / f"results/eval_{split}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / f"docs/eval_{split}_auto.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    with open(ROOT / f"results/errors_{split}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["method", "error", "doc_id", "kind", "type", "id_or_head", "tail"])
        w.writerows([r + [""] * (7 - len(r)) for r in rows])
    for name in runs:
        a, e, rr = res[name]["ALL"], res[name]["ENTITIES"], res[name]["RELATIONS"]
        print(f"{name:14s} ALL F1 {a['F1']:.3f} (P {a['P']:.3f}, R {a['R']:.3f}) | сутності F1 {e['F1']:.3f} | "
              f"відношення F1 {rr['F1']:.3f} (P {rr['P']:.3f}, R {rr['R']:.3f}) | "
              f"статті·відн. F1 {res[name]['articles·RELATIONS']['F1']:.3f} | реєстри·відн. F1 {res[name]['registers·RELATIONS']['F1']:.3f}")
    print(json.dumps(res["_meta"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
