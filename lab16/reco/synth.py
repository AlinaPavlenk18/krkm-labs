"""Синтетичні дані взаємодій (реальних журналів KMS немає) — задокументовано в docs/reco_design.md."""
import argparse
import csv
import math
from datetime import datetime, timedelta

import numpy as np

from reco.data import DATA, build_graph, kg_edges, load_items, zone

START, END = datetime(2026, 10, 1), datetime(2026, 11, 6, 23, 0)
TYPE_W = {"regulation": 3, "faq": 3, "procedure": 2, "register": 2, "model_card": 2, "kb_article": 1.5, "glossary": 1.5,
          "forecast_log": 1.5, "policy": 1, "project_doc": 0.6, "report": 0.6}
DISP_CONCEPTS = ["C:перевантаження", "C:рівні завантаження", "C:перерозподіл", "C:ланцюг живлення", "C:договірний ліміт"]
ANALYST = {"forecasting": ["C:прогноз", "C:похибка прогнозу", "C:перенавчання", "C:погода", "ForecastModel_LSTM1",
                           "ForecastModel_LSTM2", "ForecastModel_LSTM3", "ForecastModel_GRU1", "ForecastModel_VAR1",
                           "ForecastModel_ARIMA1"],
           "graph": ["C:граф знань", "C:PageRank", "C:спільноти", "C:онтологія", "C:архітектура", "C:суперечності"],
           "quality": ["C:якість даних", "C:лічильники", "C:несправності", "C:суперечності", "C:доступ"]}
ENGINEER = ["C:лічильники", "C:несправності", "C:якість даних", "C:споживачі", "C:погода"]
DISPATCHERS = [f"Dispatcher_{i}" for i in range(1, 7)]


def dispatcher_interests(d):
    subs = set(zone(d))
    for a, b, rel in kg_edges():
        if rel in ("живить", "прогнозується моделлю") and (a in subs or b in subs):
            subs |= {a, b}
    return sorted(subs | {d}) + DISP_CONCEPTS


def make_users(rng):
    users = []

    def add(uid, role, group, interests, cold):
        k = max(3, int(len(interests) * rng.uniform(0.6, 0.85)))
        own = list(rng.choice(interests, size=k, replace=False))
        extra = list(rng.choice(sorted({e for it in load_items().values() for e in it["entities"]}), size=2, replace=False))
        users.append({"user_id": uid, "role": role, "group": group, "interests": own + extra, "cold": cold})

    n = 0
    for d in DISPATCHERS:
        for j in range(6):
            n += 1
            add(f"u{n:03d}", "dispatcher", d, dispatcher_interests(d), cold=(j == 5))
    for grp, ints in ANALYST.items():
        for j in range(6 + (2 if grp == "forecasting" else 1 if grp == "graph" else 1)):
            n += 1
            add(f"u{n:03d}", "analyst", grp, ints, cold=(j >= 6))
    for j in range(14):
        n += 1
        add(f"u{n:03d}", "engineer", "ami", ENGINEER, cold=(j >= 12))
    return users


def generate(seed=42):
    rng = np.random.default_rng(seed)
    items = load_items()
    g = build_graph()
    ids = sorted(i for i, it in items.items() if it["sensitivity"] != "restricted")
    avail = {i: datetime.fromisoformat(items[i]["date"]) for i in ids}
    prior = np.array([TYPE_W.get(items[i]["type"], 1) / (1 + 0.15 * items[i]["pos"]) for i in ids])
    by_ent = {}
    for i in ids:
        for e in items[i]["entities"]:
            by_ent.setdefault(e, []).append(i)
    users = make_users(rng)
    rows = []
    for u in users:
        t0 = datetime(2026, 10, 29) + timedelta(days=float(rng.uniform(0, 7))) if u["cold"] else \
            START + timedelta(days=float(rng.uniform(0, 14)))
        n_ev = int(rng.poisson(8 if u["cold"] else 24)) + 3
        times = sorted(t0 + timedelta(seconds=float(rng.uniform(0, (END - t0).total_seconds()))) for _ in range(n_ev))
        last = None
        for t in times:
            ok = [i for i in ids if avail[i] <= t]
            okset = set(ok)
            r, pick, mech = rng.random(), None, None
            if r < 0.45:
                cands = [e for e in u["interests"] if any(i in okset for i in by_ent.get(e, []))]
                if cands:
                    e = cands[rng.integers(len(cands))]
                    pool = [i for i in by_ent[e] if i in okset]
                    pick, mech = pool[rng.integers(len(pool))], "task"
            elif r < 0.70 and last:
                nb = [n for n in g.neighbors(last) if n in okset]
                via = [i for e in items[last]["entities"] for i in by_ent.get(e, []) if i in okset and i != last]
                pool = nb + via[:20]
                if pool:
                    pick, mech = pool[rng.integers(len(pool))], "follow"
            elif r < 0.90:
                w = np.array([prior[k] if ids[k] in okset else 0 for k in range(len(ids))])
                pick, mech = ids[rng.choice(len(ids), p=w / w.sum())], "popular"
            if pick is None:
                pick, mech = ok[rng.integers(len(ok))], "explore"
            rows.append({"user_id": u["user_id"], "item_id": pick, "ts": t.isoformat(timespec="minutes"), "mechanism": mech})
            last = pick
    return users, rows


def save(users, rows, seed):
    DATA.mkdir(exist_ok=True)
    suf = "" if seed == 42 else f"_s{seed}"
    with open(DATA / f"users{suf}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "role", "group", "cold", "interests"])
        for u in users:
            w.writerow([u["user_id"], u["role"], u["group"], int(u["cold"]), ";".join(u["interests"])])
    with open(DATA / f"interactions{suf}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["user_id", "item_id", "ts", "mechanism"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["ts"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    users, rows = generate(a.seed)
    save(users, rows, a.seed)
    print(f"користувачів {len(users)} (нових {sum(u['cold'] for u in users)}), подій {len(rows)}, "
          f"елементів у журналі {len({r['item_id'] for r in rows})}")
