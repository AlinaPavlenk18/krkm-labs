"""Рекомендатори: популярнісний baseline, графовий (Personalized PageRank), embeddings (kNN), гібрид (зважений RRF)."""
import math
import sys
from collections import Counter
from datetime import datetime

import networkx as nx
import numpy as np

from reco.data import REPO, build_graph, label, load_items

# kb10 «Класифікація конфіденційності та правила доступу»: зовнішній — public; аналітик (і інженер) — public + internal;
# диспетчер — ще restricted своєї зони; керівник служби — усе.
ROLE_SENS = {"external": {"public"}, "analyst": {"public", "internal"}, "engineer": {"public", "internal"},
             "dispatcher": {"public", "internal", "restricted_zone"}, "head": {"public", "internal", "restricted"}}
HALF_LIFE_DAYS = 14


class Filters:
    """Фільтри якості й прав: роль → допустима sensitivity; verified; свіжість (max_age_days); уже переглянуті."""

    def __init__(self, role="analyst", verified_only=True, max_age_days=None, exclude_seen=True, respect_type_freshness=False,
                 zone=()):
        self.role, self.verified_only, self.max_age_days, self.zone = role, verified_only, max_age_days, set(zone)
        self.exclude_seen, self.respect_type_freshness = exclude_seen, respect_type_freshness

    def allowed(self, it, seen, now=None):
        if now is not None and it["date"] > now.date().isoformat():
            return False, "not_published"                         
        allowed = ROLE_SENS.get(self.role, {"public"})
        if it["sensitivity"] == "restricted" and "restricted" not in allowed:
            subs = {e for e in it["entities"] if e.startswith("Substation_")}
            if not ("restricted_zone" in allowed and subs and subs <= self.zone):   
                return False, "sensitivity"
        elif it["sensitivity"] not in allowed:
            return False, "sensitivity"
        if self.verified_only and not it["verified"]:
            return False, "verified"
        if self.max_age_days is not None and it["age_days"] > self.max_age_days:
            return False, "freshness"
        if self.respect_type_freshness and not it["fresh"]:
            return False, "freshness"
        if self.exclude_seen and it["id"] in seen:
            return False, "seen"
        return True, None

    def apply(self, scores, seen, now=None):
        items = load_items()
        out, dropped = {}, Counter()
        for i, s in scores.items():
            ok, why = self.allowed(items[i], seen, now)
            if ok:
                out[i] = s
            else:
                dropped[why] += 1
        return out, dropped


def _weights(history, now):
    w = Counter()
    for i, t in history:
        w[i] += 0.5 ** (max(0.0, (now - t).total_seconds()) / 86400 / HALF_LIFE_DAYS)
    return w


def _top(scores, k):
    return [i for i, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]]


class Popularity:
    name = "popularity"

    def fit(self, train):                          # train: [(user, item, ts)]
        self.cnt = Counter(i for _, i, _ in train)
        return self

    def scores(self, ctx):
        items = load_items()
        return {i: self.cnt.get(i, 0) + 1e-6 * (1 / (1 + items[i]["pos"])) for i in items}


class GraphPPR:
    """Personalized PageRank від переглянутих розділів (з часовим згасанням) і сутностей профілю."""
    name = "graph"

    def __init__(self, alpha=0.85, profile_weight=1.0):
        self.alpha, self.profile_weight = alpha, profile_weight
        self.g = build_graph()

    def fit(self, train):
        return self

    def scores(self, ctx):
        pers = Counter(_weights(ctx["history"], ctx["now"]))
        for e in ctx.get("profile", []):
            if e in self.g:
                pers[e] += self.profile_weight
        if not pers:
            return {}
        pr = nx.pagerank(self.g, alpha=self.alpha, personalization=dict(pers), max_iter=200, tol=1e-8)
        return {n: v for n, v in pr.items() if self.g.nodes[n]["kind"] == "item"}


class EmbeddingKNN:
    """kNN за косинусом між профілем користувача (зважене середнє переглянутих) і розділами; e5-small з ЛР10–11."""
    name = "embedding"

    def __init__(self):
        sys.path.insert(0, str(REPO / "lab11" / "src"))
        from encoders import Encoder               
        self.enc = Encoder("e5-small")
        items = load_items()
        self.ids = sorted(items)
        self.idx = {i: k for k, i in enumerate(self.ids)}
        self.X = self.enc.encode_passages([f"{items[i]['title']}. {items[i]['section']}. {items[i]['text']}" for i in self.ids])

    def fit(self, train):
        return self

    def scores(self, ctx):
        w = _weights(ctx["history"], ctx["now"])
        if w:
            v = sum(wt * self.X[self.idx[i]] for i, wt in w.items())
        elif ctx.get("profile"):
            v = self.enc.encode_queries(["; ".join(label(e) for e in ctx["profile"])])[0]
        else:
            return {}
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = self.X @ v
        return {i: float(sims[k]) for k, i in enumerate(self.ids)}


class Hybrid:
    """Зважений RRF: score(i) = Σ_m w_m / (k + rank_m(i)); ранги після фільтрів."""
    name = "hybrid"

    def __init__(self, parts, weights, k=60):
        self.parts, self.weights, self.k = parts, weights, k

    def fit(self, train):
        for p in self.parts.values():
            p.fit(train)
        return self

    def scores(self, ctx):
        out = Counter()
        for name, m in self.parts.items():
            s = m.scores(ctx)
            for r, i in enumerate(_top(s, len(s))):
                out[i] += self.weights.get(name, 0) / (self.k + r + 1)
        return dict(out)


def recommend(model, ctx, k=10, filters=None):
    filters = filters or Filters(ctx.get("role", "analyst"))
    seen = {i for i, _ in ctx["history"]}
    s, dropped = filters.apply(model.scores(ctx), seen, ctx.get("now"))
    return _top(s, k), dropped


def make(name, emb=None, weights=None, k=60):
    if name == "popularity":
        return Popularity()
    if name == "graph":
        return GraphPPR()
    if name == "embedding":
        return emb or EmbeddingKNN()
    if name == "hybrid":
        return Hybrid({"graph": GraphPPR(), "embedding": emb or EmbeddingKNN(), "popularity": Popularity()},
                      weights or {"graph": 1.0, "embedding": 1.0, "popularity": 0.3}, k)
    raise ValueError(name)
