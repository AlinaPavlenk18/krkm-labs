"""CLI рекомендацій і демонстрація фільтрів.

  python -m reco.cli recommend --user u001 [--method hybrid] [--k 5] [--explain]
  python -m reco.cli filters --user u013          # той самий користувач з різними ролями й фільтрами
  python -m reco.cli cold-user --role dispatcher --group Dispatcher_2
  python -m reco.cli cold-doc --doc kb16 --user u013    # новий документ (опубліковано 07.11) без жодної взаємодії
"""
import argparse
import json
from datetime import datetime

from reco.data import LAB, load_items, zone
from reco.eval import END, load, profile, rrf, split
from reco.explain import explain
from reco.models import EmbeddingKNN, Filters, GraphPPR, Popularity, _top

NOW = END                                  


def setup():
    users, ev = load(42)
    train, hist, _ = split(ev, NOW, NOW)
    w = json.loads((LAB / "results" / "eval.json").read_text(encoding="utf-8"))["seed42"] \
        if (LAB / "results" / "eval.json").exists() else {"hybrid_weights": {"graph": 1, "embedding": 1, "popularity": 0.3},
                                                          "rrf_k": 60}
    models = {"popularity": Popularity().fit(train), "graph": GraphPPR(), "embedding": EmbeddingKNN()}
    return users, hist, models, w["hybrid_weights"], w["rrf_k"]


def scores(models, method, ctx, w, kk):
    comp = {n: m.scores(ctx) for n, m in models.items()}
    return rrf(comp, w, kk) if method == "hybrid" else comp[method]


def show(ids, items, hist_items=(), prof=(), expl=False):
    for r, i in enumerate(ids, 1):
        it = items[i]
        print(f"{r}. {i:<10} [{it['sensitivity']}, {it['date']}, verified={it['verified']}] {it['title'][:45]} › {it['section'][:40]}")
        if expl:
            print("   " + explain(i, hist_items, prof, use_llm=True)["final"][:300])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recommend"); r.add_argument("--user", required=True); r.add_argument("--method", default="hybrid")
    r.add_argument("--k", type=int, default=5); r.add_argument("--explain", action="store_true")
    f = sub.add_parser("filters"); f.add_argument("--user", required=True)
    c = sub.add_parser("cold-user"); c.add_argument("--role", default="dispatcher"); c.add_argument("--group", default="Dispatcher_2")
    d = sub.add_parser("cold-doc"); d.add_argument("--doc", default="kb16"); d.add_argument("--user", required=True)
    a = ap.parse_args()
    users, hist, models, w, kk = setup()
    items = load_items()
    if a.cmd == "recommend":
        u = users[a.user]
        ctx = {"role": u["role"], "history": hist[a.user], "now": NOW, "profile": []}
        s, dropped = Filters(u["role"], zone=zone(u["group"]) if u["role"] == "dispatcher" else ()).apply(scores(models, a.method, ctx, w, kk), {i for i, _ in ctx["history"]}, NOW)
        print(f"{a.user} ({u['role']}, {u['group']}), переглянуто {len({i for i, _ in ctx['history']})}; відфільтровано {dict(dropped)}")
        show(_top(s, a.k), items, [i for i, _ in sorted(ctx["history"], key=lambda x: x[1])], expl=a.explain)
    elif a.cmd == "filters":
        u = users[a.user]
        ctx = {"role": u["role"], "history": hist[a.user], "now": NOW, "profile": []}
        sc = scores(models, "hybrid", ctx, w, kk)
        seen = {i for i, _ in ctx["history"]}
        for title, flt in [("роль external (лише public)", Filters("external")),
                           (f"роль {u['role']} (public + internal), verified", Filters(u["role"])),
                           (f"роль {u['role']} без фільтра verified", Filters(u["role"], verified_only=False)),
                           ("роль head — керівник служби (усі рівні)", Filters("head")),
                           ("роль dispatcher своєї зони (restricted лише зони)", Filters("dispatcher", zone=zone(u["group"]) if u["role"] == "dispatcher" else ())),
                           (f"роль {u['role']}, свіжість ≤ 20 днів", Filters(u["role"], max_age_days=20))]:
            s, dropped = flt.apply(sc, seen, NOW)
            top = _top(s, 10)
            print(f"\n== {title}: допустимо {len(s)}, відкинуто {dict(dropped)}")
            print("   top-10:", ", ".join(top))
            print("   restricted у top-10:", sum(items[i]["sensitivity"] == "restricted" for i in top),
                  "| неперевірених:", sum(not items[i]["verified"] for i in top),
                  "| старших за 20 днів:", sum(items[i]["age_days"] > 20 for i in top))
    elif a.cmd == "cold-user":
        u = {"role": a.role, "group": a.group}
        prof = profile(u)
        ctx = {"role": a.role, "history": [], "now": NOW, "profile": prof}
        print(f"новий користувач: {a.role}, {a.group}; профіль онбордингу: {prof}")
        comp = {n: m.scores(ctx) for n, m in models.items()}
        s, _ = Filters(a.role).apply(rrf(comp, {"graph": 1, "embedding": 1, "popularity": 1}, 60), set(), NOW)
        show(_top(s, 5), items, prof=prof, expl=True)
    elif a.cmd == "cold-doc":
        u = users[a.user]
        ctx = {"role": u["role"], "history": hist[a.user], "now": NOW, "profile": []}
        seen = {i for i, _ in ctx["history"]}
        new = [i for i in items if items[i]["doc"] == a.doc]
        print(f"новий документ {a.doc}: {len(new)} розділів, взаємодій у журналі: 0")
        for n in ("popularity", "graph", "embedding", "hybrid"):
            s, _ = Filters(u["role"]).apply(scores(models, n, ctx, w, kk), seen, NOW)
            order = _top(s, len(s))
            ranks = sorted(order.index(i) + 1 for i in new if i in order)
            print(f"  {n:<11} найкращий ранг розділу {a.doc}: {ranks[0] if ranks else '—'} з {len(order)}; у top-10: "
                  f"{sum(r <= 10 for r in ranks)}")


if __name__ == "__main__":
    main()
