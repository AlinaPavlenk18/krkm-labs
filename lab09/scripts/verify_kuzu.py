import csv
import json
import re
import shutil
import tempfile
from pathlib import Path

import kuzu

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
Q = ROOT / "queries"

NODE_SCHEMA = {
    "Consumer": "id STRING, name STRING, subLabel STRING, category STRING, contractLimit DOUBLE, address STRING, source STRING",
    "Meter": "id STRING, name STRING, status STRING, meterType STRING, readingInterval INT64, source STRING",
    "Measurement": "id STRING, name STRING, consumptionValue DOUBLE, voltage DOUBLE, timestamp TIMESTAMP, source STRING",
    "WeatherCondition": "id STRING, name STRING, temperature DOUBLE, cloudCover STRING, source STRING",
    "ForecastModel": "id STRING, name STRING, subLabel STRING, modelType STRING, accuracy DOUBLE, trainingDate DATE, source STRING",
    "Forecast": "id STRING, name STRING, forecastPeriod STRING, errorPercentage DOUBLE, predictedConsumption DOUBLE, source STRING",
    "Dispatcher": "id STRING, name STRING, qualification STRING, shift STRING, source STRING",
    "Substation": "id STRING, name STRING, nominalCapacity DOUBLE, currentLoad DOUBLE, source STRING",
    "Region": "id STRING, name STRING, source STRING",
}
RELS = [("HAS_METER", "Consumer", "Meter"), ("CONNECTED_TO", "Consumer", "Substation"),
        ("RECORDED", "Meter", "Measurement"), ("INFLUENCES", "WeatherCondition", "Measurement"),
        ("AFFECTS_MODEL", "WeatherCondition", "ForecastModel"), ("TRAINED_ON", "ForecastModel", "Measurement"),
        ("GENERATED", "ForecastModel", "Forecast"), ("USES_FORECAST", "Dispatcher", "Forecast"),
        ("MANAGES", "Dispatcher", "Substation"), ("FEEDS", "Substation", "Substation"),
        ("LOCATED_IN", "Substation", "Region"), ("FORECAST_FOR", "Forecast", "Substation")]

PARAMS = {
    "q01": {"substation": "Substation_7"},
    "q06": {"model": "ForecastModel_LSTM2"},
    "q08": {"meter": "Meter_AMI77410"},
    "q09": {"substation": "Substation_1"},
}

OVERRIDE = {
    "q04": lambda q: q.replace("collect(x)[0]", "collect(x)[1]").replace(
        "WITH c, m, x ORDER BY x.timestamp DESC", "WITH c, m, x ORDER BY x.timestamp DESC SKIP 0"),
    "q08": lambda q: (q.replace("MATCH (m:Meter {id: $meter}), (d:Dispatcher)\n", "")
                       .replace("p = shortestPath((m)-[:HAS_METER|CONNECTED_TO|FEEDS|MANAGES*..8]-(d))",
                                "p = (m:Meter {id: $meter})-[:HAS_METER|CONNECTED_TO|FEEDS|MANAGES* SHORTEST 1..8]-(d:Dispatcher)")
                       .replace("[n IN nodes(p) | n.id]", "properties(nodes(p), 'id')")
                       .replace("[r IN relationships(p) | type(r)]", "list_transform(rels(p), r -> label(r))")),
}


def strip(text):
    body = [l for l in text.splitlines() if not l.strip().startswith("//")]
    return "\n".join(body).strip().rstrip(";")


def build(db_dir):
    db = kuzu.Database(str(db_dir))
    con = kuzu.Connection(db)
    for lab, cols in NODE_SCHEMA.items():
        con.execute(f"CREATE NODE TABLE {lab}({cols}, PRIMARY KEY(id))")
        con.execute(f"COPY {lab} FROM '{DATA / ('nodes_' + lab.lower() + '.csv')}' (header=true)")
    for t, a, b in RELS:
        con.execute(f"CREATE REL TABLE {t}(FROM {a} TO {b}, source STRING, confidence DOUBLE, validFrom DATE)")
        
        src = DATA / f"rels_{t.lower()}.csv"
        con.execute(f"COPY {t} FROM '{src}' (header=true)")
    return db, con


def to_py(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, list):
        return [to_py(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def main():
    tmp = Path(tempfile.mkdtemp()) / "kuzu_db"
    db, con = build(tmp)
    out = {}
    n = con.execute("MATCH (n) RETURN count(n)").get_next()[0]
    r = con.execute("MATCH ()-[r]->() RETURN count(r)").get_next()[0]
    out["_counts"] = {"nodes": n, "relationships": r}
    for f in sorted(Q.glob("q*.cypher")):
        key = f.name[:3]
        parts = [strip(x) for x in f.read_text(encoding="utf-8").split(";\n") if strip(x)]
        for k, q in enumerate(parts, 1):
            q = OVERRIDE.get(key, lambda x: x)(q)
            res = con.execute(q, PARAMS.get(key, {}))
            cols = res.get_column_names()
            rows = []
            while res.has_next():
                rows.append(dict(zip(cols, [to_py(v) for v in res.get_next()])))
            out[f.stem + (f"#M{k}" if len(parts) > 1 else "")] = rows
    shutil.rmtree(tmp.parent, ignore_errors=True)
    (ROOT / "docs" / "expected_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    res = main()
    for k, rows in res.items():
        print(f"\n== {k}")
        if isinstance(rows, dict):
            print(rows)
            continue
        for row in rows:
            print(row)
