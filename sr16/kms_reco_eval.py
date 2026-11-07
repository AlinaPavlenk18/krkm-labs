"""Оцінювання рекомендацій Hub «Прогнозування енергоспоживання»: популярнісний, контентний і графовий підходи.

Дані — журнал переглядів фрагментів знань ЛР16 (reco/synth.py, seed 42–46), каталог — 295 розділів документів ЛР14.
Часове розбиття: train < 27.10.2026, test 27.10–06.11 (як у ЛР16). Підходи:
  popularity — кількість train-переглядів;
  content    — TF-IDF слів розділу (назва документа + розділ + текст), профіль — зважене середнє переглянутих;
  graph      — Personalized PageRank ЛР16 на графі «розділ – сутність – зв'язки КГ».
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lab16"))
from reco.data import load_items                                  
from reco.eval import CUT, END, load, ndcg, profile, split         
from reco.models import Filters, GraphPPR, Popularity, _top, _weights  

RES = Path(__file__).resolve().parent / "results"
ITEMS = load_items()
IDS = sorted(ITEMS)


class Content:
    name = "content"

    def __init__(self):
        docs = [f"{ITEMS[i]['title']} {ITEMS[i]['section']} {ITEMS[i]['text']}" for i in IDS]
        self.X = TfidfVectorizer(sublinear_tf=True, min_df=2, ngram_range=(1, 2)).fit_transform(docs)
        self.idx = {i: k for k, i in enumerate(IDS)}

    def fit(self, train):
        return self

    def scores(self, ctx):
        w = _weights(ctx["history"], ctx["now"])
        if not w:
            return {}
        v = sum(wt * self.X[self.idx[i]] for i, wt in w.items())
        s = (self.X @ v.T).toarray().ravel()
        return {i: float(s[k]) for k, i in enumerate(IDS)}


def ranked(model, ctx, k=10, fallback=None):
    s = model.scores(ctx) or (fallback.scores(ctx) if fallback else {})
    f, _ = Filters(ctx["role"]).apply(s, {i for i, _ in ctx["history"]}, ctx["now"])
    return _top(f, k)


def ents(i):
    return set(ITEMS[i]["entities"]) | {"doc:" + ITEMS[i]["doc"]}


def ild(r):
    pairs = [(a, b) for x, a in enumerate(r) for b in r[x + 1:]]
    return float(np.mean([1 - len(ents(a) & ents(b)) / max(1, len(ents(a) | ents(b))) for a, b in pairs])) if pairs else 0.0


def metrics(recs, rel, train, now):
    cnt = Counter(i for _, i, _ in train)
    tot = len(train)
    elig = [i for i in IDS if Filters("analyst").allowed(ITEMS[i], set(), now)[0]]
    pct = {i: (np.searchsorted(sorted(cnt.get(j, 0) for j in elig), cnt.get(i, 0), side="right")) / len(elig) for i in elig}
    per = np.array([(len(set(r[:5]) & rel[u]) / 5, ndcg(r, rel[u])) for u, r in recs.items()])
    flat = [i for r in recs.values() for i in r]
    exp = Counter(flat)
    x = np.sort(np.array([exp.get(i, 0) for i in elig], float))
    gini = float(1 - 2 * np.sum(np.cumsum(x) / x.sum()) / len(x) + 1 / len(x)) if x.sum() else 0.0
    return {"precision@5": float(per[:, 0].mean()), "nDCG@10": float(per[:, 1].mean()),
            "coverage": len(exp) / len(elig),
            "novelty": float(np.mean([-math.log2((cnt.get(i, 0) + 1) / (tot + len(ITEMS))) for i in flat])),
            "ILD": float(np.mean([ild(r) for r in recs.values()])),
            "docs_in_top10": float(np.mean([len({ITEMS[i]["doc"] for i in r}) for r in recs.values()])),
            "pop_percentile": float(np.mean([pct.get(i, 0) for i in flat])), "gini": gini}, per


def boot(per, n=1000):
    g = np.random.default_rng(42)
    return {m: [round(float(np.percentile([per[g.integers(0, len(per), len(per)), j].mean() for _ in range(n)], q)), 4)
                for q in (2.5, 97.5)] for j, m in enumerate(("precision@5", "nDCG@10"))}


def mmr_rank(model, ctx, lam, k=10):
    s = model.scores(ctx)
    f, _ = Filters(ctx["role"]).apply(s, {i for i, _ in ctx["history"]}, ctx["now"])
    cand = _top(f, 60)
    if not cand:
        return []
    v = np.array([f[c] for c in cand]); v = (v - v.min()) / (np.ptp(v) + 1e-12)
    chosen = []
    while len(chosen) < min(k, len(cand)):
        best = max((c for c in cand if c not in chosen), key=lambda c: lam * v[cand.index(c)] - (1 - lam) * max(
            (len(ents(c) & ents(o)) / max(1, len(ents(c) | ents(o))) for o in chosen), default=0))
        chosen.append(best)
    return chosen


def run(seed, full):
    users, ev = load(seed)
    train, hist, rel = split(ev, CUT, END)
    warm = [u for u in users if hist.get(u) and rel.get(u)]
    pop, con, gr = Popularity().fit(train), Content(), GraphPPR()
    ctx = {u: {"role": users[u]["role"], "history": hist[u], "now": CUT, "profile": []} for u in warm}
    out, cis = {}, {}
    for m in (pop, con, gr):
        recs = {u: ranked(m, ctx[u]) for u in warm}
        out[m.name], per = metrics(recs, rel, train, CUT)
        if full:
            cis[m.name] = boot(per)
    res = {"seed": seed, "eval_users": len(warm), "train": len(train), "metrics": out, "ci95": cis}
    if not full:
        return res
    # MMR поверх графа: різноманіття ціною точності
    res["mmr_graph"] = {}
    for lam in (1.0, 0.7, 0.5):
        recs = {u: mmr_rank(gr, ctx[u], lam) for u in warm}
        res["mmr_graph"][lam] = metrics(recs, rel, train, CUT)[0]
    # холодні користувачі k-shot (перші k переглядів після приходу), k = 0 → популярність або профіль онбордингу
    cold = [u for u in users if users[u]["cold"] == "1"]
    evs = defaultdict(list)
    for u, i, t in ev:
        if u in cold and CUT <= t < END:
            evs[u].append((t, i))
    res["cold_users"] = {}
    for k in (0, 1, 3, 5):
        h, rl = {}, {}
        for u in cold:
            seq = sorted(evs[u])
            if len(seq) <= k:
                continue
            h[u] = [(i, t) for t, i in seq[:k]]
            rl[u] = {i for _, i in seq[k:]} - {i for i, _ in h[u]}
        us = [u for u in h if rl[u]]
        now = {u: (h[u][-1][1] if h[u] else CUT) for u in us}
        row = {"users": len(us)}
        for m in (pop, con, gr):
            recs = {u: ranked(m, {"role": users[u]["role"], "history": h[u], "now": now[u], "profile": []}, fallback=pop)
                    for u in us}
            row[m.name] = {x: round(v, 4) for x, v in metrics(recs, rl, train, CUT)[0].items() if x in ("precision@5", "nDCG@10")}
        if k == 0:
            recs = {u: ranked(gr, {"role": users[u]["role"], "history": [], "now": CUT, "profile": profile(users[u])}) for u in us}
            row["graph+профіль"] = {x: round(v, 4) for x, v in metrics(recs, rl, train, CUT)[0].items() if x in ("precision@5", "nDCG@10")}
        res["cold_users"][k] = row
    # нові документи: 3 документи з найбільшою кількістю test-переглядів, без train-взаємодій
    per_doc = Counter(ITEMS[i]["doc"] for u in rel for i in rel[u])
    cdocs = [d for d, _ in per_doc.most_common(3)]
    tr2 = [e for e in train if ITEMS[e[1]]["doc"] not in cdocs]
    h2 = defaultdict(list)
    for u, i, t in tr2:
        h2[u].append((i, t))
    pop2 = Popularity().fit(tr2)
    res["cold_docs"], res["cold_items"] = cdocs, {}
    for m in (pop2, con, gr):
        pairs = hits = shown = 0
        for u in warm:
            r = ranked(m, {"role": users[u]["role"], "history": h2[u], "now": CUT, "profile": []}, fallback=pop2)
            tgt = {i for i in rel[u] if ITEMS[i]["doc"] in cdocs}
            pairs += len(tgt); hits += len(tgt & set(r)); shown += sum(ITEMS[i]["doc"] in cdocs for i in r)
        res["cold_items"][m.name] = {"pairs": pairs, "cold_item_recall@10": round(hits / max(1, pairs), 4),
                                     "cold_share_in_top10": round(shown / (10 * len(warm)), 4)}
    return res


def main():
    RES.mkdir(exist_ok=True)
    runs = [run(s, s == 42) for s in (42, 43, 44, 45, 46)]
    names = ("popularity", "content", "graph")
    keys = ("precision@5", "nDCG@10", "coverage", "novelty", "ILD", "docs_in_top10", "pop_percentile", "gini")
    summ = {n: {k: [round(float(np.mean([r["metrics"][n][k] for r in runs])), 4),
                    round(float(np.std([r["metrics"][n][k] for r in runs], ddof=1)), 4)] for k in keys} for n in names}
    first = runs[0]
    first["metrics"] = {n: {k: round(v, 4) for k, v in m.items()} for n, m in first["metrics"].items()}
    first["mmr_graph"] = {l: {k: round(v, 4) for k, v in m.items()} for l, m in first["mmr_graph"].items()}
    (RES / "sr16_results.json").write_text(json.dumps({"seed42": first, "repeats_mean_sd": summ}, ensure_ascii=False,
                                                      indent=1), encoding="utf-8")
    print(json.dumps(first["metrics"], ensure_ascii=False, indent=1)); print("CI:", json.dumps(first["ci95"]))
    print("повтори:", json.dumps(summ, ensure_ascii=False))
    print("холодні користувачі:", json.dumps(first["cold_users"], ensure_ascii=False))
    print("нові документи", first["cold_docs"], json.dumps(first["cold_items"], ensure_ascii=False))
    print("MMR:", json.dumps(first["mmr_graph"], ensure_ascii=False))
    plot(first, summ)


def plot(f, s):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names, col = ["popularity", "content", "graph"], ["#9aa5b1", "#59a14f", "#4c78a8"]
    fig, ax = plt.subplots(1, 4, figsize=(13, 3.2))
    for a, m in zip(ax[:2], ("precision@5", "nDCG@10")):
        v = [f["metrics"][n][m] for n in names]
        e = [[v[i] - f["ci95"][n][m][0] for i, n in enumerate(names)], [f["ci95"][n][m][1] - v[i] for i, n in enumerate(names)]]
        a.bar(names, v, yerr=e, capsize=4, color=col); a.set_title(m + " (seed 42, 95 % ДІ)", fontsize=9)
    ax[2].bar(names, [f["metrics"][n]["coverage"] for n in names], color=col); ax[2].set_title("coverage", fontsize=9)
    ks = sorted(f["cold_users"], key=int)
    for n, c in zip(names, col):
        ax[3].plot([int(k) for k in ks], [f["cold_users"][k][n]["nDCG@10"] for k in ks], "o-", color=c, label=n)
    ax[3].set_title("нові користувачі: nDCG@10", fontsize=9); ax[3].set_xlabel("k перших переглядів"); ax[3].legend(fontsize=7)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False); a.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(RES / "sr16_metrics.png", dpi=160)


if __name__ == "__main__":
    main()
