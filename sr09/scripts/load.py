"""
СР9 · Крок 3. Завантаження датасету в сховище (час завантаження теж фіксується).

  python scripts/load.py neo4j      # LPG: UNWIND-пакети через Bolt, унікальні обмеження на id
  python scripts/load.py memgraph   # те саме для Memgraph (Bolt, порт 7688)
  python scripts/load.py graphdb    # RDF: bench.ttl → REST /repositories/<repo>/statements
"""
import csv
import json
import sys
import time

from common import DATA, LABELS, NUMERIC, RELS, bolt_driver, graphdb_endpoint

BATCH = 500


def rows(path):
    out = []
    for r in csv.DictReader(path.open(encoding="utf-8")):
        out.append({k: (float(v) if k in NUMERIC else v) for k, v in r.items()})
    return out


def load_bolt(engine, force):
    drv = bolt_driver(engine)
    t0 = time.perf_counter()
    with drv.session() as s:
        n_lab9 = s.run("MATCH (n) WHERE n.source IS NOT NULL RETURN count(n) AS c").single()["c"]
        if n_lab9 and not force:
            sys.exit(f"У базі {n_lab9} вузлів із властивістю source (схоже на граф ЛР9). "
                     "Запустіть окремий інстанс або додайте --force.")
        s.run("MATCH (n) DETACH DELETE n").consume()
        for lab in LABELS:
            if engine == "neo4j":
                s.run(f"CREATE CONSTRAINT bench_{lab.lower()}_id IF NOT EXISTS FOR (n:{lab}) REQUIRE n.id IS UNIQUE").consume()
            else:
                try:
                    s.run(f"CREATE INDEX ON :{lab}(id)").consume()
                    s.run(f"CREATE CONSTRAINT ON (n:{lab}) ASSERT n.id IS UNIQUE").consume()
                except Exception as e:     
                    if "exist" not in str(e).lower():
                        raise
        if engine == "neo4j":
            s.run("CREATE INDEX bench_meter_status IF NOT EXISTS FOR (m:Meter) ON (m.status)").consume()
        else:
            try:
                s.run("CREATE INDEX ON :Meter(status)").consume()
            except Exception as e:
                if "exist" not in str(e).lower():
                    raise
        t_schema = time.perf_counter()
        for lab in LABELS:
            data = rows(DATA / f"nodes_{lab.lower()}.csv")
            for i in range(0, len(data), BATCH):
                s.run(f"UNWIND $rows AS r CREATE (n:{lab}) SET n = r", rows=data[i:i + BATCH]).consume()
        for typ, a, b in RELS:
            data = rows(DATA / f"rels_{typ.lower()}.csv")
            for i in range(0, len(data), BATCH):
                s.run(f"UNWIND $rows AS r MATCH (a:{a} {{id: r.start}}) MATCH (b:{b} {{id: r.end}}) "
                      f"CREATE (a)-[:{typ}]->(b)", rows=data[i:i + BATCH]).consume()
        t1 = time.perf_counter()
        n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        r = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    drv.close()
    return {"engine": engine, "nodes": n, "relationships": r,
            "schema_s": round(t_schema - t0, 2), "load_s": round(t1 - t_schema, 2)}


def load_graphdb():
    import requests
    url, repo = graphdb_endpoint()
    t0 = time.perf_counter()
    requests.delete(f"{url}/repositories/{repo}/statements").raise_for_status()
    body = (DATA / "bench.ttl").read_bytes()
    t_schema = time.perf_counter()
    requests.post(f"{url}/repositories/{repo}/statements", data=body,
                  headers={"Content-Type": "text/turtle;charset=UTF-8"}).raise_for_status()
    t1 = time.perf_counter()
    size = requests.get(f"{url}/repositories/{repo}/size").text.strip()
    return {"engine": "graphdb", "triples": int(size), "clear_s": round(t_schema - t0, 2),
            "load_s": round(t1 - t_schema, 2)}


if __name__ == "__main__":
    engine = sys.argv[1]
    force = "--force" in sys.argv
    res = load_graphdb() if engine == "graphdb" else load_bolt(engine, force)
    print(json.dumps(res, ensure_ascii=False))
    out = DATA.parent / "docs" / f"load_{engine}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
