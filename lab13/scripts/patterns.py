"""Результат 5: асоціативні правила X → Y над розділами документів (транзакція = розділ, предмети = сутності).

Метрики: support, confidence, lift. Перевірки: випадковість — перестановочний тест (1000 перестановок, seed 42);
механізм — чи є між X і Y відношення у витягнутому графі (data/extracted.jsonl); стабільність — lift окремо
в статтях і в реєстрах та bootstrap-інтервал lift. Вихід: results/patterns.json, docs/patterns_auto.md
"""
import json, random, re, sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.extract_rules import build_nlp, entities, sections  

MIN_PAIR, MIN_CONF, PERM, BOOT = 3, 0.6, 1000, 500


def transactions():
    nlp = build_nlp()
    T = []
    for l in open(ROOT / "data/docs.jsonl", encoding="utf-8"):
        d = json.loads(l)
        for head, a, b in sections(d["text"]):
            items = {c for t, c, _, _ in entities(nlp, d["text"][a:b])}
            if len(items) >= 2:
                T.append({"doc": d["doc_id"], "section": head.strip("# ").strip(), "items": items})
    return T


def rule_stats(T, x, y):
    n = len(T)
    nx = sum(x in t["items"] for t in T)
    ny = sum(y in t["items"] for t in T)
    nxy = sum(x in t["items"] and y in t["items"] for t in T)
    if not nx or not ny:
        return None
    conf = nxy / nx
    return {"n": n, "nx": nx, "ny": ny, "nxy": nxy, "support": round(nxy / n, 4),
            "confidence": round(conf, 3), "lift": round(conf / (ny / n), 2)}


def perm_p(T, x, y, obs, rnd):
    idx = list(range(len(T)))
    nx = sum(x in t["items"] for t in T)
    ys = {i for i, t in enumerate(T) if y in t["items"]}
    hits = 0
    for _ in range(PERM):
        xs = set(rnd.sample(idx, nx))      # частоти X і Y збережено, розташування X — випадкове
        hits += len(xs & ys) >= obs
    return (hits + 1) / (PERM + 1)


def main():
    rnd = random.Random(42)
    T = transactions()
    freq = Counter(i for t in T for i in t["items"])
    pairs = Counter(p for t in T for p in combinations(sorted(t["items"]), 2))
    graph = defaultdict(set)
    for l in open(ROOT / "data/extracted.jsonl", encoding="utf-8"):
        s = json.loads(l)
        if s["kind"] == "relation":
            graph[frozenset((s["head"], s["tail"]))].add(s["type"])
    rules = []
    for (a, b), nab in pairs.items():
        if nab < MIN_PAIR:
            continue
        for x, y in ((a, b), (b, a)):
            st = rule_stats(T, x, y)
            if st["confidence"] < MIN_CONF or st["lift"] <= 1:
                continue
            art = [t for t in T if not t["doc"].startswith("gen")]
            reg = [t for t in T if t["doc"].startswith("gen")]
            sa, sr = rule_stats(art, x, y), rule_stats(reg, x, y)
            boots = []
            for _ in range(BOOT):
                s = [T[rnd.randrange(len(T))] for _ in T]
                bs = rule_stats(s, x, y)
                if bs and bs["nxy"]:
                    boots.append(bs["lift"])
            boots.sort()
            ci = (boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]) if boots else (None, None)
            rules.append({"X": x, "Y": y, **st, "p_perm": round(perm_p(T, x, y, st["nxy"], rnd), 4),
                          "mechanism": sorted(graph.get(frozenset((x, y)), [])),
                          "lift_articles": sa["lift"] if sa and sa["nxy"] else None,
                          "lift_registers": sr["lift"] if sr and sr["nxy"] else None,
                          "lift_ci95": ci, "docs": sorted({t["doc"] for t in T if x in t["items"] and y in t["items"]})})
    rules.sort(key=lambda r: (-r["lift"], -r["nxy"]))
    out = {"transactions": len(T), "items": len(freq), "min_pair": MIN_PAIR, "min_conf": MIN_CONF, "rules": rules}
    (ROOT / "results/patterns.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# Асоціативні правила (автоматичний звіт)", "", f"Транзакцій (розділів із ≥ 2 сутностями): {len(T)}; "
          f"предметів: {len(freq)}; поріг: спільних розділів ≥ {MIN_PAIR}, confidence ≥ {MIN_CONF}, lift > 1.", "",
          "| X → Y | nXY | support | conf | lift | p (перест.) | механізм у графі | lift статті / реєстри | 95 % ДІ lift | документи |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rules:
        md.append(f"| {r['X']} → {r['Y']} | {r['nxy']} | {r['support']} | {r['confidence']} | {r['lift']} | {r['p_perm']} | "
                  f"{', '.join(r['mechanism']) or '—'} | {r['lift_articles']} / {r['lift_registers']} | "
                  f"{r['lift_ci95'][0]}–{r['lift_ci95'][1]} | {', '.join(r['docs'])} |")
    (ROOT / "docs/patterns_auto.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"транзакцій {len(T)}, правил {len(rules)}")
    for r in rules[:25]:
        print(f"{r['X']:22s}→ {r['Y']:22s} nxy={r['nxy']:2d} conf={r['confidence']:.2f} lift={r['lift']:6.2f} "
              f"p={r['p_perm']:.3f} mech={r['mechanism']} art/reg={r['lift_articles']}/{r['lift_registers']} ci={r['lift_ci95']}")


if __name__ == "__main__":
    main()
