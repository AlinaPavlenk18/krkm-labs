"""Офлайн-оцінка з часовим розбиттям.  python -m reco.eval [--seeds 42 43 44 45 46] [--boot 1000]

Розбиття (без витоків): train — події до 27.10.2026 00:00, test — з 27.10 до 06.11 включно. Рекомендації будуються
один раз на момент 27.10 лише з train; документи з датою після цього моменту відкидає фільтр not_published;
популярність рахується тільки з train. Ваги гібриду підбираються на валідації всередині train (train до 20.10,
перевірка 20–26.10) і лише потім застосовуються до test.
Метрики: precision@5, recall@5, nDCG@10 (бінарна релевантність: нові для користувача елементи з test), coverage
(частка допустимого каталогу в об'єднанні top-10), novelty (середня самоінформація −log2 p(i) за train).
Невизначеність: бутстреп-інтервали 95 % за користувачами (seed 42) і 5 повторів генерації даних (seed 42–46).
Холодний старт: нові користувачі (профіль з онбордингу) і нові документи (3 документи без train-взаємодій).
"""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

from reco.data import DATA, LAB, load_items
from reco.models import EmbeddingKNN, Filters, GraphPPR, Popularity, _top
from reco.synth import ANALYST, ENGINEER, dispatcher_interests, generate, save

CUT, VAL_CUT, END = datetime(2026, 10, 27), datetime(2026, 10, 20), datetime(2026, 11, 7)
RES = LAB / "results"
K_RRF = [10, 60]
GRID = [{"graph": g, "embedding": e, "popularity": p} for g in (0, 0.5, 1, 2) for e in (0, 0.5, 1, 2)
        for p in (0, 0.3, 1) if g + e > 0]
METRICS = ["precision@5", "recall@5", "nDCG@10", "coverage", "novelty"]


def load(seed):
    suf = "" if seed == 42 else f"_s{seed}"
    if not (DATA / f"interactions{suf}.csv").exists():
        save(*generate(seed), seed)
    users = {r["user_id"]: r for r in csv.DictReader(open(DATA / f"users{suf}.csv", encoding="utf-8"))}
    ev = [(r["user_id"], r["item_id"], datetime.fromisoformat(r["ts"]))
          for r in csv.DictReader(open(DATA / f"interactions{suf}.csv", encoding="utf-8"))]
    return users, ev


def profile(u):
    if u["role"] == "dispatcher":
        return dispatcher_interests(u["group"])
    return ANALYST[u["group"]] if u["role"] == "analyst" else ENGINEER


def split(ev, cut, end):
    train = [e for e in ev if e[2] < cut]
    test = [e for e in ev if cut <= e[2] < end]
    hist, rel = defaultdict(list), defaultdict(set)
    for u, i, t in train:
        hist[u].append((i, t))
    for u, i, _ in test:
        if i not in {x for x, _ in hist[u]}:
            rel[u].add(i)
    return train, hist, rel


def ndcg(rec, rel, k=10):
    dcg = sum(1 / math.log2(r + 2) for r, i in enumerate(rec[:k]) if i in rel)
    idcg = sum(1 / math.log2(r + 2) for r in range(min(k, len(rel))))
    return dcg / idcg if idcg else 0.0


def per_user(recs, rel):
    return {u: {"precision@5": len(set(r[:5]) & rel[u]) / 5, "recall@5": len(set(r[:5]) & rel[u]) / len(rel[u]),
                "nDCG@10": ndcg(r, rel[u])} for u, r in recs.items()}


def aggregate(recs, rel, train, cut, role="analyst"):
    pu = per_user(recs, rel)
    items = load_items()
    f = Filters(role)
    eligible = [i for i, it in items.items() if f.allowed(it, set(), cut)[0]]
    cnt, tot = Counter(i for _, i, _ in train), len(train)
    p = {i: (cnt.get(i, 0) + 1) / (tot + len(items)) for i in items}
    allr = [i for r in recs.values() for i in r[:10]]
    out = {m: float(np.mean([v[m] for v in pu.values()])) for m in ("precision@5", "recall@5", "nDCG@10")}
    out["coverage"] = len(set(allr)) / len(eligible)
    out["novelty"] = float(np.mean([-math.log2(p[i]) for i in allr])) if allr else 0.0
    return out, pu


def boot(pu, n=1000, seed=42):
    rng = np.random.default_rng(seed)
    us = sorted(pu)
    out = {}
    for m in ("precision@5", "recall@5", "nDCG@10"):
        v = np.array([pu[u][m] for u in us])
        bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(n)]
        out[m] = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
    return out


class RolePopularity(Popularity):
    name = "role_popularity"

    def __init__(self, users):
        self.users = users

    def fit(self, train):
        self.by_role = defaultdict(Counter)
        for u, i, _ in train:
            self.by_role[self.users[u]["role"]][i] += 1
        return self

    def scores(self, ctx):
        c = self.by_role.get(ctx["role"], Counter())
        return {i: c.get(i, 0) + 1e-6 for i in load_items()}


def component_scores(models, users, hist, us, now, cold=False):
    out = {}
    for u in us:
        ctx = {"role": users[u]["role"], "history": [] if cold else hist[u], "now": now,
               "profile": profile(users[u]) if cold else []}
        out[u] = ({n: m.scores(ctx) for n, m in models.items()}, ctx)
    return out


def ranked(scores, ctx, k=10):
    f = Filters(ctx["role"])
    s, _ = f.apply(scores, {i for i, _ in ctx["history"]}, ctx["now"])
    return _top(s, k)


def rrf(comp, w, k):
    out = Counter()
    for n, s in comp.items():
        if w.get(n):
            for r, i in enumerate(_top(s, len(s))):
                out[i] += w[n] / (k + r + 1)
    return dict(out)


def run_split(users, ev, cut, end, emb, weights=None, kk=60, cold_items=()):
    train, hist, rel = split(ev, cut, end)
    if cold_items:                                         # нові документи: прибираємо їхні train-взаємодії
        train = [e for e in train if load_items()[e[1]]["doc"] not in cold_items]
        hist = defaultdict(list)
        for u, i, t in train:
            hist[u].append((i, t))
    warm = [u for u in users if hist.get(u) and rel.get(u)]
    models = {"popularity": Popularity().fit(train), "graph": GraphPPR(), "embedding": emb}
    comp = component_scores(models, users, hist, warm, cut)
    recs = {n: {u: ranked(comp[u][0][n], comp[u][1]) for u in warm} for n in models}
    grid = None
    if weights is None:                                    # підбір ваг гібриду лише на валідації
        vtrain, vhist, vrel = split(ev, VAL_CUT, cut)
        vwarm = [u for u in users if vhist.get(u) and vrel.get(u)]
        vmodels = {"popularity": Popularity().fit(vtrain), "graph": GraphPPR(), "embedding": emb}
        vcomp = component_scores(vmodels, users, vhist, vwarm, VAL_CUT)
        grid = []
        for kk_ in K_RRF:
            for w in GRID:
                r = {u: ranked(rrf(vcomp[u][0], w, kk_), vcomp[u][1]) for u in vwarm}
                grid.append((float(np.mean([ndcg(r[u], vrel[u]) for u in vwarm])), kk_, w))
        best = max(grid, key=lambda x: x[0])
        weights, kk = best[2], best[1]
    recs["hybrid"] = {u: ranked(rrf(comp[u][0], weights, kk), comp[u][1]) for u in warm}
    return train, rel, warm, recs, weights, kk, grid


def cold_users(users, ev, emb):
    train, hist, rel = split(ev, CUT, END)
    cold = [u for u in users if users[u]["cold"] == "1" and rel.get(u) and not hist.get(u)]
    models = {"popularity": Popularity().fit(train), "role_popularity": RolePopularity(users).fit(train),
              "graph": GraphPPR(), "embedding": emb}
    comp = component_scores(models, users, hist, cold, CUT, cold=True)
    recs = {n: {u: ranked(comp[u][0][n], comp[u][1]) for u in cold} for n in models}
    recs["hybrid"] = {u: ranked(rrf(comp[u][0], {"graph": 1, "embedding": 1, "role_popularity": 1}, 60), comp[u][1])
                      for u in cold}
    return {n: aggregate(r, rel, train, CUT)[0] for n, r in recs.items()}, len(cold)


def cold_items(users, ev, emb, weights, kk, seed):
    _, _, rel = split(ev, CUT, END)
    items = load_items()
    docs = sorted({items[i]["doc"] for u in rel for i in rel[u]})
    pairs_per_doc = Counter(items[i]["doc"] for u in rel for i in rel[u])
    cdocs = [d for d, _ in pairs_per_doc.most_common(3)]                 # 3 документи з найбільшою кількістю test-взаємодій
    train, rel2, warm, recs, *_ = run_split(users, ev, CUT, END, emb, weights, kk, cold_items=cdocs)
    out = {}
    for n, r in recs.items():
        pairs = [(u, i) for u in warm for i in rel2[u] if items[i]["doc"] in cdocs]
        hits = [i in r[u][:10] for u, i in pairs]
        out[n] = {"pairs": len(pairs), "cold_item_recall@10": round(float(np.mean(hits)), 4) if hits else 0.0,
                  "cold_items_in_any_top10": len({i for u in warm for i in r[u][:10] if items[i]["doc"] in cdocs})}
    return cdocs, out


def plot(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(res["metrics"])
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.6))
    for a, m in zip(ax, ("precision@5", "recall@5", "nDCG@10")):
        v = [res["metrics"][n][m] for n in names]
        lo = [v[k] - res["ci"][n][m][0] for k, n in enumerate(names)]
        hi = [res["ci"][n][m][1] - v[k] for k, n in enumerate(names)]
        a.bar(names, v, yerr=[lo, hi], capsize=4, color=["#9aa5b1", "#4c78a8", "#59a14f", "#e15759"])
        a.set_title(m)
        a.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    RES.mkdir(exist_ok=True)
    emb = EmbeddingKNN()
    rep = {}
    for seed in a.seeds:
        users, ev = load(seed)
        train, rel, warm, recs, w, kk, grid = run_split(users, ev, CUT, END, emb)
        res = {"seed": seed, "n_users": len(users), "n_events": len(ev), "n_train": len(train),
               "n_test": sum(CUT <= e[2] < END for e in ev), "eval_users": len(warm), "hybrid_weights": w, "rrf_k": kk,
               "metrics": {}, "ci": {}}
        for n, r in recs.items():
            m, pu = aggregate(r, rel, train, CUT)
            res["metrics"][n] = {k: round(v, 4) for k, v in m.items()}
            if seed == a.seeds[0]:
                res["ci"][n] = boot(pu, a.boot)
        if seed == a.seeds[0]:
            res["validation_top5"] = [{"nDCG@10": round(g, 4), "k": k, "weights": ww}
                                      for g, k, ww in sorted(grid, key=lambda x: -x[0])[:5]]
            res["cold_users"], res["n_cold_users"] = cold_users(users, ev, emb)
            res["cold_docs"], res["cold_items"] = cold_items(users, ev, emb, w, kk, seed)
            res["example_recs"] = {n: {u: recs[n][u][:5] for u in warm[:3]} for n in recs}
            plot(res, RES / "reco_metrics.png")
        rep[seed] = res
        print(f"seed {seed}: користувачів в оцінці {len(warm)}, гібрид {w}, k={kk}")
        for n, m in res["metrics"].items():
            print(f"  {n:<11} " + "  ".join(f"{k}={v:.3f}" for k, v in m.items()))
    summ = {n: {m: [round(float(np.mean([rep[s]["metrics"][n][m] for s in rep])), 4),
                    round(float(np.std([rep[s]["metrics"][n][m] for s in rep], ddof=1)), 4) if len(rep) > 1 else 0.0]
                for m in METRICS} for n in rep[a.seeds[0]]["metrics"]}
    first = rep[a.seeds[0]]
    (RES / "eval.json").write_text(json.dumps({"seed42": first, "repeats_mean_sd": summ,
                                               "seeds": a.seeds}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nСереднє ± sd за повторами:")
    for n, m in summ.items():
        print(f"  {n:<11} " + "  ".join(f"{k}={v[0]:.3f}±{v[1]:.3f}" for k, v in m.items()))
    print("\nХолодні користувачі:", json.dumps(first["cold_users"], ensure_ascii=False))
    print("Холодні документи", first["cold_docs"], json.dumps(first["cold_items"], ensure_ascii=False))


if __name__ == "__main__":
    main()
