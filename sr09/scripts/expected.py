"""Очікувані результати 5 запитів: Cypher — у вбудованій Kùzu, SPARQL — у rdflib. Перевірка еквівалентності.
Вихід: docs/expected.json"""
import csv, json, tempfile, re
from pathlib import Path
import kuzu
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
SCHEMA = {
 "Region": "id STRING, name STRING", "Substation": "id STRING, name STRING, nominalCapacity DOUBLE, currentLoad DOUBLE, region STRING",
 "Dispatcher": "id STRING, name STRING, qualification STRING, shift STRING",
 "Consumer": "id STRING, name STRING, category STRING, contractLimit DOUBLE", "Meter": "id STRING, name STRING, status STRING, meterType STRING",
 "WeatherCondition": "id STRING, name STRING, temperature DOUBLE, cloudCover STRING",
 "Measurement": "id STRING, name STRING, consumptionValue DOUBLE, voltage DOUBLE, timestamp STRING",
 "ForecastModel": "id STRING, name STRING, modelType STRING, accuracy DOUBLE",
 "Forecast": "id STRING, name STRING, errorPercentage DOUBLE, forecastPeriod STRING"}
RELS = [("HAS_METER","Consumer","Meter"),("CONNECTED_TO","Consumer","Substation"),("RECORDED","Meter","Measurement"),
 ("INFLUENCES","WeatherCondition","Measurement"),("AFFECTS_MODEL","WeatherCondition","ForecastModel"),
 ("TRAINED_ON","ForecastModel","Measurement"),("GENERATED","ForecastModel","Forecast"),("USES_FORECAST","Dispatcher","Forecast"),
 ("MANAGES","Dispatcher","Substation"),("FEEDS","Substation","Substation"),("LOCATED_IN","Substation","Region"),
 ("FORECAST_FOR","Forecast","Substation")]


def norm(v):
    if hasattr(v, "toPython"):
        v = v.toPython()
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) or type(v).__name__ == "Decimal":
        f = float(v)
        return int(f) if f.is_integer() else round(f, 4)
    return str(v)


def kuzu_con():
    db = kuzu.Database(str(Path(tempfile.mkdtemp()) / "db")); con = kuzu.Connection(db)
    for lab, cols in SCHEMA.items():
        con.execute(f"CREATE NODE TABLE {lab}({cols}, PRIMARY KEY(id))")
        con.execute(f"COPY {lab} FROM '{D / ('nodes_' + lab.lower() + '.csv')}' (header=true)")
    for t, a, b in RELS:
        con.execute(f"CREATE REL TABLE {t}(FROM {a} TO {b})")
        con.execute(f"COPY {t} FROM '{D / ('rels_' + t.lower() + '.csv')}' (header=true)")
    return db, con


def to_kuzu(q):
    """Діалект Kùzu: UNWIND списку вузлів не підтримується, тож для B4 — еквівалентний запит з *0..10."""
    if "UNWIND [root] + down" in q:
        return ("MATCH (:Substation {id: 'Substation_1'})-[:FEEDS*0..10]->(s:Substation) WITH DISTINCT s "
                "OPTIONAL MATCH (c:Consumer)-[:CONNECTED_TO]->(s) RETURN s.id AS substation, count(c) AS consumers ORDER BY substation")
    return q


def main():
    Q = json.loads((ROOT / "queries" / "bench_queries.json").read_text(encoding="utf-8"))
    db, con = kuzu_con()
    g = Graph(); g.parse(D / "bench.ttl")
    out = {}
    for q in Q:
        r = con.execute(to_kuzu(q["cypher"])); cols = r.get_column_names(); cy = []
        while r.has_next():
            cy.append({c: norm(v) for c, v in zip(cols, r.get_next())})
        sp = [{str(k): norm(row[k]) for k in row.labels} for row in g.query(q["sparql"])]
        key = lambda rows: sorted(tuple(r.get(k) for k in q["key"]) for r in rows)
        same = key(cy) == key(sp)
        out[q["id"]] = {"rows": len(cy), "cypher_vs_sparql_equal": same, "result": cy}
        print(q["id"], len(cy), len(sp), "EQUAL" if same else "DIFF")
        if not same:
            print(" cy", key(cy)[:5]); print(" sp", key(sp)[:5])
    (ROOT / "docs" / "expected.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
