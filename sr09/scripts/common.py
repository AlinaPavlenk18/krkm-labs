import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

NUMERIC = {"nominalCapacity", "currentLoad", "contractLimit", "temperature", "consumptionValue",
           "voltage", "accuracy", "errorPercentage"}
LABELS = ["Region", "Substation", "Dispatcher", "Consumer", "Meter", "WeatherCondition",
          "Measurement", "ForecastModel", "Forecast"]
RELS = [("HAS_METER", "Consumer", "Meter"), ("CONNECTED_TO", "Consumer", "Substation"),
        ("RECORDED", "Meter", "Measurement"), ("INFLUENCES", "WeatherCondition", "Measurement"),
        ("AFFECTS_MODEL", "WeatherCondition", "ForecastModel"), ("TRAINED_ON", "ForecastModel", "Measurement"),
        ("GENERATED", "ForecastModel", "Forecast"), ("USES_FORECAST", "Dispatcher", "Forecast"),
        ("MANAGES", "Dispatcher", "Substation"), ("FEEDS", "Substation", "Substation"),
        ("LOCATED_IN", "Substation", "Region"), ("FORECAST_FOR", "Forecast", "Substation")]


def bolt_driver(engine):
    from neo4j import GraphDatabase
    if engine == "neo4j":
        return GraphDatabase.driver(os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
                                    auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
    return GraphDatabase.driver(os.environ.get("MEMGRAPH_URI", "bolt://localhost:7688"),
                                auth=(os.environ.get("MEMGRAPH_USER", ""), os.environ.get("MEMGRAPH_PASSWORD", "")))


def graphdb_endpoint():
    url = os.environ.get("GRAPHDB_URL", "http://localhost:7200").rstrip("/")
    return url, os.environ.get("GRAPHDB_REPO", "energy-bench")


def norm(v):
    if isinstance(v, dict) and "value" in v:         
        t, dt, val = v.get("type"), v.get("datatype", ""), v["value"]
        if t == "uri":
            return val.split("#")[-1]
        if any(x in dt for x in ("integer", "decimal", "double", "float", "int", "long")):
            f = float(val)
            return int(f) if f.is_integer() else round(f, 4)
        return val
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        f = float(v)
        return int(f) if f.is_integer() else round(f, 4)
    return str(v)
