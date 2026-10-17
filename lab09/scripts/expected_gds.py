import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

G = nx.MultiGraph()
label = {}
name = {}
for f in DATA.glob("nodes_*.csv"):
    for r in csv.DictReader(f.open(encoding="utf-8")):
        lab = {"forecastmodel": "ForecastModel", "weathercondition": "WeatherCondition"}.get(
            f.stem[6:], f.stem[6:].capitalize())
        G.add_node(r["id"])
        label[r["id"]] = lab
        name[r["id"]] = r["name"]
for f in DATA.glob("rels_*.csv"):
    for r in csv.DictReader(f.open(encoding="utf-8")):
        G.add_edge(r["start"], r["end"], type=f.stem[5:].upper())

d, iters, tol = 0.85, 20, 1e-7
deg = dict(G.degree())
pr = {v: 1 - d for v in G}
for it in range(iters):
    new = {}
    for v in G:
        s = 0.0
        for u in G.neighbors(v):
            s += pr[u] * G.number_of_edges(u, v) / deg[u]
        new[v] = (1 - d) + d * s
    delta = max(abs(new[v] - pr[v]) for v in G)
    pr = new
    if delta < tol:
        break
ran_iters = it + 1
top = sorted(pr.items(), key=lambda kv: -kv[1])[:10]

# ---- Louvain
simple = nx.Graph()
simple.add_nodes_from(G)
for u, v in G.edges():
    w = simple[u][v]["weight"] + 1 if simple.has_edge(u, v) else 1
    simple.add_edge(u, v, weight=w)
comms = nx.community.louvain_communities(simple, weight="weight", resolution=1, seed=42)
comms = sorted(comms, key=len, reverse=True)
modularity = nx.community.modularity(simple, comms, weight="weight")
comm_info = []
for i, c in enumerate(comms):
    labs = Counter(label[v] for v in c)
    subs = sorted([v for v in c if label[v] == "Substation"], key=lambda x: int(x.split("_")[1]))
    hubs = sorted(c, key=lambda v: -pr[v])[:3]
    comm_info.append({"community": i, "size": len(c), "labels": dict(labs.most_common()),
                      "substations": subs, "topByPageRank": hubs,
                      "regions": sorted(v for v in c if label[v] == "Region"),
                      "dispatchers": sorted(v for v in c if label[v] == "Dispatcher"),
                      "models": sorted(v for v in c if label[v] == "ForecastModel")})


by_label = defaultdict(list)
for v, s in pr.items():
    by_label[label[v]].append(s)
avg_by_label = {k: round(sum(x) / len(x), 3) for k, x in sorted(by_label.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))}

out = {
    "pagerank_iterations": ran_iters,
    "pagerank_top10": [{"rank": i + 1, "id": v, "label": label[v], "name": name[v], "score": round(s, 4),
                        "degree": deg[v]} for i, (v, s) in enumerate(top)],
    "pagerank_avg_by_label": avg_by_label,
    "louvain_communities": len(comms),
    "louvain_modularity": round(modularity, 4),
    "communities": comm_info,
}
(ROOT / "docs" / "expected_gds.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
