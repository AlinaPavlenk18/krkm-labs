"""
Перетворює data/triples_final.csv (RDF-триплети) на CSV для LOAD CSV у Neo4j (LPG).

Правила відображення RDF → LPG (див. docs/cq_mapping.md, табл. «Онтологія ЛР7 → схема LPG»):
  * rdf:type <Клас>               → мітка вузла (+ додаткова мітка для підкласу);
  * datatype property             → властивість вузла;
  * object property               → зв'язок; обернені пари зберігаються ОДНИМ зв'язком;
  * data property :region (рядок) → окремий вузол :Region + зв'язок LOCATED_IN;
  * провенанс триплета            → властивості зв'язку source / confidence / validFrom.

Вихід: data/nodes_<label>.csv, data/rels_<TYPE>.csv
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "triples_final.csv"
OUT = ROOT / "data"

CLASS_MAP = {
    "ResidentialConsumer": ("Consumer", "Residential"),
    "CommercialConsumer": ("Consumer", "Commercial"),
    "IndustrialConsumer": ("Consumer", "Industrial"),
    "Consumer": ("Consumer", ""),
    "Meter": ("Meter", ""),
    "Measurement": ("Measurement", ""),
    "WeatherCondition": ("WeatherCondition", ""),
    "MachineLearningModel": ("ForecastModel", "MLModel"),
    "StatisticalModel": ("ForecastModel", "StatisticalModel"),
    "ForecastModel": ("ForecastModel", ""),
    "Forecast": ("Forecast", ""),
    "Dispatcher": ("Dispatcher", ""),
    "Substation": ("Substation", ""),
}

REL_MAP = {
    "hasMeter": ("HAS_METER", False),
    "belongsToConsumer": ("HAS_METER", True),
    "connectedToSubstation": ("CONNECTED_TO", False),
    "servesConsumer": ("CONNECTED_TO", True),
    "measuredByMeter": ("RECORDED", True),          # Meter -RECORDED-> Measurement
    "generatesMeasurement": ("RECORDED", False),
    "influencesMeasurement": ("INFLUENCES", False),
    "influencesModel": ("AFFECTS_MODEL", False),
    "trainedOnMeasurement": ("TRAINED_ON", False),
    "measurementUsedForTraining": ("TRAINED_ON", True),
    "generatedByModel": ("GENERATED", True),        # ForecastModel -GENERATED-> Forecast
    "generatesForecast": ("GENERATED", False),
    "usesForecast": ("USES_FORECAST", False),
    "forecastUsedBy": ("USES_FORECAST", True),
    "managedByDispatcher": ("MANAGES", True),       # Dispatcher -MANAGES-> Substation
    "managesSubstation": ("MANAGES", False),
    "upstreamOf": ("FEEDS", False),
    "downstreamOf": ("FEEDS", True),
    "forecastForSubstation": ("FORECAST_FOR", False),
}

NODE_COLS = {
    "Consumer": ["id", "name", "subLabel", "category", "contractLimit", "address", "source"],
    "Meter": ["id", "name", "status", "meterType", "readingInterval", "source"],
    "Measurement": ["id", "name", "consumptionValue", "voltage", "timestamp", "source"],
    "WeatherCondition": ["id", "name", "temperature", "cloudCover", "source"],
    "ForecastModel": ["id", "name", "subLabel", "modelType", "accuracy", "trainingDate", "source"],
    "Forecast": ["id", "name", "forecastPeriod", "errorPercentage", "predictedConsumption", "source"],
    "Dispatcher": ["id", "name", "qualification", "shift", "source"],
    "Substation": ["id", "name", "nominalCapacity", "currentLoad", "source"],
    "Region": ["id", "name", "source"],
}
REGION_ID = {"Львівська область": "Region_Lviv", "Волинська область": "Region_Volyn",
             "Закарпатська область": "Region_Zakarpattia", "Тернопільська область": "Region_Ternopil",
             "Рівненська область": "Region_Rivne", "Івано-Франківська область": "Region_IvanoFrankivsk"}
PROP_RENAME = {"skos:prefLabel": "name", "consumerCategory": "category", "meterStatus": "status"}

rows = list(csv.DictReader(SRC.open(encoding="utf-8")))

nodes = {}                      # id -> dict
labels = {}                     # id -> main label
rels = defaultdict(dict)        # TYPE -> {(start,end): props}

for r in rows:
    if r["predicate"] == "rdf:type":
        main, sub = CLASS_MAP[r["object"]]
        labels[r["subject"]] = main
        n = nodes.setdefault(r["subject"], {"id": r["subject"]})
        n["subLabel"] = sub
        n.setdefault("source", r["source"])

for r in rows:
    s, p, o = r["subject"], r["predicate"], r["object"]
    if p == "rdf:type":
        continue
    if r["object_type"] == "literal":
        if p == "region":                           
            rid = REGION_ID[o]
            nodes.setdefault(rid, {"id": rid, "name": o, "source": "derived:lab09(region literal)"})
            labels[rid] = "Region"
            rels["LOCATED_IN"][(s, rid)] = {"source": r["source"], "confidence": "1.0",
                                            "validFrom": ""}
            continue
        nodes[s][PROP_RENAME.get(p, p)] = o
    else:
        typ, flip = REL_MAP[p]
        a, b = (o, s) if flip else (s, o)
        rels[typ][(a, b)] = {"source": r["source"], "confidence": r["confidence"],
                             "validFrom": r["valid_from"]}

by_label = defaultdict(list)
for nid, n in nodes.items():
    by_label[labels[nid]].append(n)
for lab, items in by_label.items():
    cols = NODE_COLS[lab]
    with (OUT / f"nodes_{lab.lower()}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for n in sorted(items, key=lambda x: x["id"]):
            w.writerow({c: n.get(c, "") for c in cols})

for typ, pairs in rels.items():
    with (OUT / f"rels_{typ.lower()}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["start", "end", "source", "confidence", "validFrom"])
        for (a, b), pr in sorted(pairs.items()):
            w.writerow([a, b, pr["source"], pr["confidence"], pr["validFrom"]])

print("nodes:", {k: len(v) for k, v in sorted(by_label.items())}, "total", len(nodes))
print("rels :", {k: len(v) for k, v in sorted(rels.items())}, "total", sum(len(v) for v in rels.values()))
