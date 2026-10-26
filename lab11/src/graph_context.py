"""Результат 2. Entity linking запиту до вузлів графа знань ЛР9 і витяг підграфа в контекст LLM.

Бекенди графа:
  Neo4jGraph — граф ЛР9 у Neo4j (основний; NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD);
  CsvGraph   — ті самі вузли й зв'язки з CSV ЛР9 (data/graph) у пам'яті: резерв і перевірка коду без сервера.
Кроки:
  1) entity linking — регулярні вирази за назвами та синонімами: «ПС №5», «підстанція №5», «п'ята підстанція»,
     «магістральна підстанція» (корінь ланцюга FEEDS), «диспетчер №3», «LSTM №2» / «LSTM2», «AMI-77410»,
     «споживач №3310», назви областей, дати прогнозів і погоди;
  2) підграф — сусіди на 1 крок + 2-й крок лише через «змістовні» зв'язки (без розгалуження через області,
     погоду й вимірювання), ліміт graph_max_facts фактів; спершу факти 1-го кроку;
  3) лінеаризація — кожен зв'язок окремим рядком з ID факту [g1], [g2] … та ID вузлів;
     адреси споживачів (restricted) додаються лише для ролей із доступом до restricted.
"""
import csv
import os
import re
from collections import defaultdict
from pathlib import Path

from config import allowed

GRAPH_DIR = Path(__file__).resolve().parents[1] / "data" / "graph"
LABEL_BY_FILE = {"consumer": "Consumer", "meter": "Meter", "measurement": "Measurement", "weathercondition": "WeatherCondition",
                 "forecastmodel": "ForecastModel", "forecast": "Forecast", "dispatcher": "Dispatcher",
                 "substation": "Substation", "region": "Region"}
HUB_LABELS = {"Region", "WeatherCondition", "Measurement"}      
ORDINALS = ["перш", "друг", "трет", "четверт", "п'ят", "шост", "сьом", "восьм", "дев'ят", "десят", "одинадцят", "дванадцят"]


class CsvGraph:
    name = "csv"

    def __init__(self, folder=GRAPH_DIR):
        self.nodes, self.edges = {}, []
        for p in sorted(folder.glob("nodes_*.csv")):
            label = LABEL_BY_FILE[p.stem.replace("nodes_", "")]
            for r in csv.DictReader(open(p, encoding="utf-8")):
                self.nodes[r["id"]] = {"label": label, **r}
        for p in sorted(folder.glob("rels_*.csv")):
            t = p.stem.replace("rels_", "").upper()
            for r in csv.DictReader(open(p, encoding="utf-8")):
                self.edges.append((r["start"], t, r["end"], float(r.get("confidence") or 1)))
        self.adj = defaultdict(list)
        for e in self.edges:
            self.adj[e[0]].append(e)
            self.adj[e[2]].append(e)

    def all_nodes(self):
        return self.nodes

    def incident(self, node_id):
        return self.adj.get(node_id, [])

    def close(self):
        pass


class Neo4jGraph:
    name = "neo4j"

    def __init__(self):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
                                           auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
        self.driver.verify_connectivity()
        self.db = os.environ.get("NEO4J_DATABASE") or None
        self._nodes = None

    def _run(self, q, **p):
        with self.driver.session(database=self.db, default_access_mode="READ") as s:
            return [r.data() for r in s.run(q, **p)]

    def all_nodes(self):
        if self._nodes is None:
            rows = self._run("MATCH (n) WHERE n.id IS NOT NULL "
                             "RETURN n.id AS id, [l IN labels(n) WHERE l IN $main][0] AS label, properties(n) AS p",
                             main=list(LABEL_BY_FILE.values()))
            self._nodes = {r["id"]: {"label": r["label"], **{k: str(v) for k, v in r["p"].items()}} for r in rows}
        return self._nodes

    def incident(self, node_id):
        rows = self._run("MATCH (a {id: $id})-[r]-(b) RETURN startNode(r).id AS s, type(r) AS t, endNode(r).id AS e, "
                         "coalesce(r.confidence, 1.0) AS c", id=node_id)
        return [(r["s"], r["t"], r["e"], float(r["c"])) for r in rows]

    def close(self):
        self.driver.close()


def open_graph(backend=None):
    backend = backend or os.environ.get("GRAPH_BACKEND", "neo4j")
    if backend == "neo4j" and os.environ.get("NEO4J_PASSWORD"):
        try:
            return Neo4jGraph()
        except Exception as e: 
            print(f"[graph] Neo4j недоступний ({e.__class__.__name__}); використовую CSV ЛР9")
    return CsvGraph()

def _num(node_id):
    m = re.search(r"(\d+)$", node_id)
    return m.group(1) if m else None


class EntityLinker:
    def __init__(self, graph):
        self.g = graph
        nodes = graph.all_nodes()
        self.patterns = []         
        for nid, n in nodes.items():
            lab, k = n["label"], _num(nid)
            if lab == "Substation":
                self.patterns += [(rf"(?:підстанці\w*|п/ст|пс|substation)\s*(?:№|#|no\.?\s*)?\s*{k}(?!\d)", nid),
                                  (rf"\b{re.escape(nid)}\b", nid)]
                if int(k) <= len(ORDINALS):
                    self.patterns.append((rf"{ORDINALS[int(k) - 1]}\w*\s+підстанці", nid))
            elif lab == "Dispatcher":
                self.patterns += [(rf"(?:диспетчер\w*|dispatcher)\s*(?:№|#|no\.?\s*)?\s*{k}(?!\d)", nid), (rf"\b{nid}\b", nid)]
            elif lab == "ForecastModel":
                t = nid.replace("ForecastModel_", "")
                base, num = re.match(r"([A-Z]+)(\d+)", t).groups()
                self.patterns += [(rf"\b{base}\s*(?:№|#|no\.?\s*)?\s*{num}(?!\d)", nid), (rf"\b{nid}\b", nid)]
            elif lab == "Meter":
                self.patterns.append((rf"ami[-\s]?{nid.replace('Meter_AMI', '')}\b", nid))
            elif lab == "Consumer":
                self.patterns += [(rf"(?:споживач\w*|абонент\w*|consumer)\s*(?:№|#|no\.?\s*)?\s*{k}(?!\d)", nid), (rf"\b{nid}\b", nid)]
            elif lab == "Region":
                stem = n["name"].split()[0][:-3]          
                self.patterns.append((rf"{re.escape(stem.lower())}\w*", nid))
            elif lab in ("Forecast", "WeatherCondition"):
                d = re.search(r"_(\d{4})(\d{2})(\d{2})", nid)
                if d:
                    y, m, dd = d.groups()
                    word = "прогноз" if lab == "Forecast" else "погод"
                    self.patterns.append((rf"{word}\w*[^.?!]{{0,25}}?{dd}\.{m}\.{y}", nid))

        self.root = self._feeds_root()
        if self.root:
            self.patterns.append((r"(?:магістральн|головн)\w*\s+підстанц", self.root))
        self.patterns = [(re.compile(p, re.I), nid) for p, nid in self.patterns]

    def _feeds_root(self):
        nodes = self.g.all_nodes()
        subs = [n for n, v in nodes.items() if v["label"] == "Substation"]
        down = {s: [e[2] for e in self.g.incident(s) if e[1] == "FEEDS" and e[0] == s] for s in subs}
        has_parent = {c for s in subs for c in down[s]}

        def size(s, seen=()):
            return 1 + sum(size(c, seen + (s,)) for c in down[s] if c not in seen)
        roots = [s for s in subs if s not in has_parent]
        return max(roots, key=size) if roots else None

    def link(self, text, max_entities=4):
        found = []
        for rx, nid in self.patterns:
            m = rx.search(text)
            if m and nid not in [f[0] for f in found]:
                found.append((nid, m.group(0), m.start()))
        found.sort(key=lambda x: x[2])
        return [{"id": nid, "mention": mention} for nid, mention, _ in found[:max_entities]]


def _fmt(v):
    try:
        f = float(v)
        return (f"{f:.1f}".rstrip("0").rstrip(".")).replace(".", ",")
    except (TypeError, ValueError):
        return v


def describe(n, role):
    lab = n["label"]
    if lab == "Substation":
        pct = 100 * float(n["currentLoad"]) / float(n["nominalCapacity"])
        return f"{n['name']}, навантаження {_fmt(n['currentLoad'])}/{_fmt(n['nominalCapacity'])} кВт ({_fmt(round(pct, 1))} %)"
    if lab == "Dispatcher":
        return f"{n['name']}, зміна {n.get('shift', '')}"
    if lab == "ForecastModel":
        return f"{n['name']}, тип {n.get('modelType', '')}, точність {_fmt(n.get('accuracy'))} %, навчена {n.get('trainingDate', '')}"
    if lab == "Forecast":
        return f"{n['name']}, період {n.get('forecastPeriod', '')}, похибка {_fmt(n.get('errorPercentage'))} %"
    if lab == "Consumer":
        s = f"{n['name']}, договірний ліміт {_fmt(n.get('contractLimit'))} кВт"
        if allowed("restricted", role) and n.get("address"):
            s += f", адреса {n['address']}"            
        return s
    if lab == "Meter":
        return f"{n['name']}, статус {n.get('status', '')}, {n.get('meterType', '')}, інтервал {n.get('readingInterval', '')} хв"
    if lab == "Measurement":
        return f"{n['name']}, {_fmt(n.get('consumptionValue'))} кВт·год, напруга {_fmt(n.get('voltage'))} В, {n.get('timestamp', '')}"
    if lab == "WeatherCondition":
        return f"{n['name']}, {_fmt(n.get('temperature'))} °C, хмарність {n.get('cloudCover', '')}"
    return n.get("name", "")


def subgraph(graph, seeds, hops=2, max_facts=25):
    nodes = graph.all_nodes()
    seen, out = set(), []
    frontier = list(seeds)
    for hop in range(1, hops + 1):
        nxt = []
        for nid in frontier:
            if hop > 1 and nodes.get(nid, {}).get("label") in HUB_LABELS:
                continue
            for e in sorted(graph.incident(nid), key=lambda e: (e[1], e[0], e[2])):
                key = (e[0], e[1], e[2])
                if key in seen:
                    continue
                other = e[2] if e[0] == nid else e[0]
                if hop > 1 and nodes.get(other, {}).get("label") in HUB_LABELS:
                    continue                         
                seen.add(key)
                out.append((*e, hop))
                nxt.append(other)
        frontier = nxt
    out.sort(key=lambda x: x[4])                   
    return out[:max_facts]


def linearize(graph, edges, role, start=1):
    nodes = graph.all_nodes()
    lines, facts, described = [], [], set()

    def node(nid):                                 
        if nid in described:
            return nid
        described.add(nid)
        return f"{nid} «{describe(nodes[nid], role)}»"
    for i, (a, t, b, conf, hop) in enumerate(edges, start=start):
        fid = f"g{i}"
        conf_s = f" (довіра {conf:.2f})".replace(".", ",") if conf < 1 else ""
        line = f"[{fid}] {node(a)} —{t}→ {node(b)}{conf_s}"
        lines.append(line)
        facts.append({"id": fid, "start": a, "type": t, "end": b, "hop": hop, "text": line})
    return "\n".join(lines), facts


class GraphContext:
    def __init__(self, backend=None, hops=2, max_facts=25):
        self.graph = open_graph(backend)
        self.linker = EntityLinker(self.graph)
        self.hops, self.max_facts = hops, max_facts

    def build(self, question, role):
        ents = self.linker.link(question)
        if not ents:
            return {"entities": [], "facts": [], "text": ""}
        edges = subgraph(self.graph, [e["id"] for e in ents], self.hops, self.max_facts)
        text, facts = linearize(self.graph, edges, role)
        return {"entities": ents, "facts": facts, "text": text, "backend": self.graph.name}
