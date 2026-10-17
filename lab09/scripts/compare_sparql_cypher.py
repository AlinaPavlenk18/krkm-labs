"""
ЛР9 · Результат 5 · Кроки 1–2. Ті самі 5 питань у SPARQL (запити 1–5 з ЛР8, файл
data/source/lab08_queries.rq) і в Cypher; порівняння результатів і часу виконання.

SPARQL-бекенд:  rdflib + RDFS-замикання (owlrl) над ПОВНИМ набором triples_final.csv + vocabulary.ttl
                (або --fuseki URL — endpoint Fuseki з ЛР8, напр. http://localhost:3030/energy/sparql)
Cypher-бекенд:  --cypher kuzu (контроль у середовищі підготовки) або --cypher neo4j (основний)
Вихід: docs/sparql_vs_cypher_results.json
"""
import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
EF = Namespace("http://www.semanticweb.org/energy-forecasting#")

PAIRS = [
    {"id": "S1", "cq": "KQ2, KQ8", "title": "Перевантажені підстанції (≥ 85 %) і диспетчер",
     "sparql_no": 1,
     "cypher": """MATCH (d:Dispatcher)-[:MANAGES]->(s:Substation)
WHERE s.currentLoad / s.nominalCapacity >= 0.85
RETURN s.name AS name, s.currentLoad AS load, s.nominalCapacity AS capacity,
       round(100.0 * s.currentLoad / s.nominalCapacity) AS percent, d.id AS dispatcher
ORDER BY percent DESC""", "key": "name"},
    {"id": "S2", "cq": "KQ8", "title": "Підстанції з необов'язковим диспетчером (OPTIONAL)",
     "sparql_no": 2,
     "cypher": """MATCH (s:Substation)-[:LOCATED_IN]->(r:Region)
OPTIONAL MATCH (d:Dispatcher)-[:MANAGES]->(s)
RETURN s.name AS name, r.name AS region, d.id AS dispatcher, d.shift AS shift
ORDER BY name""", "key": "name"},
    {"id": "S3", "cq": "KQ3", "title": "Навантаження за регіонами (GROUP BY)",
     "sparql_no": 3,
     "cypher": """MATCH (s:Substation)-[:LOCATED_IN]->(r:Region)
RETURN r.name AS region, count(s) AS substations,
       sum(s.nominalCapacity) AS totalCapacity, sum(s.currentLoad) AS totalLoad
ORDER BY totalCapacity DESC""", "key": "region"},
    {"id": "S4", "cq": "KQ1", "title": "Усі споживачі (у SPARQL — через виведення підкласів)",
     "sparql_no": 4,
     "cypher": """MATCH (c:Consumer)
RETURN c.name AS name, c.category AS category, c.contractLimit AS limit
ORDER BY name""", "key": "name"},
    {"id": "S5", "cq": "KQ8", "title": "ASK: чи є підстанція без диспетчера?",
     "sparql_no": 5,
     "cypher": """RETURN EXISTS { MATCH (s:Substation) WHERE NOT EXISTS { MATCH (:Dispatcher)-[:MANAGES]->(s) } } AS answer""",
     "key": "answer"},
]


def load_rdf():
    g = Graph()
    g.parse(ROOT / "data" / "source" / "lab08_vocabulary.ttl", format="turtle")
    for r in csv.DictReader((ROOT / "data" / "triples_final.csv").open(encoding="utf-8")):
        s = EF[r["subject"]]
        p = RDF.type if r["predicate"] == "rdf:type" else (
            SKOS.prefLabel if r["predicate"] == "skos:prefLabel" else EF[r["predicate"]])
        if r["object_type"] == "iri":
            o = EF[r["object"]]
        elif r["lang"]:
            o = Literal(r["object"], lang=r["lang"])
        else:
            o = Literal(r["object"], datatype=XSD[r["datatype"] or "string"])
        g.add((s, p, o))
    import owlrl
    owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(g)   # rdfs:subClassOf → :Consumer тощо
    return g


def sparql_queries():
    text = (ROOT / "data" / "source" / "lab08_queries.rq").read_text(encoding="utf-8")
    blocks = [b for b in text.split("# ===== Запит ") if b.strip()]
    return {int(b.split()[0]): "\n".join(b.splitlines()[1:]).strip() for b in blocks}


def norm(v):
    if isinstance(v, URIRef):
        return str(v).split("#")[-1]
    if isinstance(v, Literal):
        v = v.toPython()
    if isinstance(v, float):
        return round(v, 2)
    if hasattr(v, "is_integer") and not isinstance(v, bool):
        try:
            return round(float(v), 2)
        except Exception:
            pass
    return v


def timed(fn, n=5):
    ts, out = [], None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        ts.append((time.perf_counter() - t0) * 1000)
    return out, round(statistics.median(ts), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cypher", choices=["kuzu", "neo4j"], default="kuzu")
    ap.add_argument("--fuseki", default=None)
    args = ap.parse_args()

    sq = sparql_queries()
    g = load_rdf() if not args.fuseki else None

    if args.cypher == "kuzu":
        import tempfile
        import verify_kuzu
        _, con = verify_kuzu.build(Path(tempfile.mkdtemp()) / "db")

        def cy(q):
            q = q.replace("EXISTS { MATCH (s:Substation) WHERE NOT EXISTS { MATCH (:Dispatcher)-[:MANAGES]->(s) } }",
                          "COUNT { MATCH (s:Substation) WHERE NOT EXISTS { MATCH (:Dispatcher)-[:MANAGES]->(s) } } > 0")
            q = q.replace("round(100.0 * s.currentLoad / s.nominalCapacity)",
                          "round(100.0 * s.currentLoad / s.nominalCapacity, 0)")   # Kùzu: round(x, n)
            if q.startswith("RETURN COUNT"):   
                q = ("MATCH (s:Substation) WHERE NOT EXISTS { MATCH (:Dispatcher)-[:MANAGES]->(s) } "
                     "RETURN count(s) > 0 AS answer")
            res = con.execute(q)
            cols = res.get_column_names()
            rows = []
            while res.has_next():
                rows.append(dict(zip(cols, res.get_next())))
            return rows
    else:
        from neo4j_common import database, driver
        drv = driver()

        def cy(q):
            with drv.session(database=database()) as s:
                return [r.data() for r in s.run(q)]

    def sp(q):
        if args.fuseki:
            import requests
            r = requests.post(args.fuseki, data={"query": q}, headers={"Accept": "application/sparql-results+json"})
            js = r.json()
            if "boolean" in js:
                return [{"answer": js["boolean"]}]
            return [{k: v["value"] for k, v in b.items()} for b in js["results"]["bindings"]]
        res = g.query(q)
        if res.type == "ASK":
            return [{"answer": bool(res.askAnswer)}]
        return [{str(k): norm(row[k]) for k in res.vars} for row in res]

    report = []
    for p in PAIRS:
        q_sp = sq[p["sparql_no"]]
        rs, ts = timed(lambda: sp(q_sp))
        rc, tc = timed(lambda: cy(p["cypher"]))
        rs_n = [{k: norm(v) for k, v in r.items()} for r in rs]
        rc_n = [{k: norm(v) for k, v in r.items()} for r in rc]
        key = p["key"]
        same_keys = sorted(map(str, (r[key] for r in rs_n))) == sorted(map(str, (r[key] for r in rc_n)))
        report.append({
            "id": p["id"], "cq": p["cq"], "title": p["title"],
            "sparql": q_sp, "cypher": p["cypher"],
            "sparql_rows": len(rs_n), "cypher_rows": len(rc_n), "keys_match": same_keys,
            "sparql_lines": len([l for l in q_sp.splitlines() if l.strip() and not l.startswith("PREFIX")]),
            "cypher_lines": len([l for l in p["cypher"].splitlines() if l.strip()]),
            "sparql_chars": len(q_sp), "cypher_chars": len(p["cypher"]),
            "sparql_ms": ts, "cypher_ms": tc,
            "sparql_result": rs_n, "cypher_result": rc_n,
        })
        print(f"{p['id']}: SPARQL {len(rs_n)} рядк. / Cypher {len(rc_n)} рядк.; ключі збігаються: {same_keys}; "
              f"час {ts} / {tc} мс")
        for a, b in zip(rs_n, rc_n):
            print("   SPARQL:", a)
            print("   Cypher:", b)
    out = ROOT / "docs" / "sparql_vs_cypher_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
