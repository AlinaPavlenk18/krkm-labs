"""
СР9 · Крок 2. Малий датасет для бенчмарку графових сховищ (≥ 500 вузлів).

Та сама схема, що в ЛР9 (9 міток, 12 типів зв'язків), але масштабована: ~660 вузлів, ~1100 зв'язків.
Генерація детермінована (SEED = 42). Дані СИНТЕТИЧНІ — це не реальні об'єкти енергомережі.

Вихід (папка data/):
  nodes_<label>.csv, rels_<type>.csv  — для Neo4j і Memgraph (завантаження scripts/load.py);
  bench.ttl                           — той самий граф у RDF (словник ЛР8) для GraphDB.
Запуск: python scripts/generate_bench.py
"""
import csv
import random
from collections import defaultdict
from pathlib import Path

SEED = 42
rng = random.Random(SEED)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)

N_SUBSTATIONS = 30
N_DISPATCHERS = 10
N_CONSUMERS = 160
N_DOUBLE_METER = 10          # споживачі з двома лічильниками
N_MEASUREMENTS = 200
N_WEATHER_DAYS = 20
N_MODELS = 8
N_FORECASTS = 60

nodes = defaultdict(list)    # label -> [dict]
rels = defaultdict(list)     # type -> [(start, end)]

REGIONS = [("Region_Lviv", "Львівська область"), ("Region_Volyn", "Волинська область"),
           ("Region_Zakarpattia", "Закарпатська область"), ("Region_Ternopil", "Тернопільська область"),
           ("Region_Rivne", "Рівненська область"), ("Region_IvanoFrankivsk", "Івано-Франківська область")]
for rid, name in REGIONS:
    nodes["Region"].append({"id": rid, "name": name})

subs_by_region = defaultdict(list)
for i in range(1, N_SUBSTATIONS + 1):
    rid, rname = REGIONS[(i - 1) % len(REGIONS)]
    cap = rng.choice([250.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1600.0, 2500.0])
    load = round(cap * rng.uniform(0.35, 0.97), 1)
    sid = f"Substation_{i}"
    nodes["Substation"].append({"id": sid, "name": f"Підстанція №{i}", "nominalCapacity": cap,
                                "currentLoad": load, "region": rname})
    rels["LOCATED_IN"].append((sid, rid))
    subs_by_region[rid].append(sid)

for rid, subs in subs_by_region.items():
    for k in range(1, len(subs)):
        parent = subs[rng.randrange(max(0, k - 2), k)]     
        rels["FEEDS"].append((parent, subs[k]))

shifts = ["ранкова", "вечірня", "нічна"]
for i in range(1, N_DISPATCHERS + 1):
    nodes["Dispatcher"].append({"id": f"Dispatcher_{i}", "name": f"Диспетчер №{i}",
                                "qualification": rng.choice(["молодший", "старший", "провідний"]),
                                "shift": shifts[i % 3]})
sub_ids = [n["id"] for n in nodes["Substation"]]
unmanaged = {"Substation_9", "Substation_27"}            
managed_by = {}
for k, sid in enumerate(sub_ids):
    if sid in unmanaged:
        continue
    d = f"Dispatcher_{k % N_DISPATCHERS + 1}"
    managed_by[sid] = d
    rels["MANAGES"].append((d, sid))

CATS = [("побутовий", 5.0, 15.0)] * 6 + [("комерційний", 40.0, 200.0)] * 3 + [("промисловий", 250.0, 900.0)]
meters = []
mno = 10000
for i in range(1, N_CONSUMERS + 1):
    cat, lo, hi = rng.choice(CATS)
    cid = f"Consumer_{i:04d}"
    nodes["Consumer"].append({"id": cid, "name": f"Споживач №{i}", "category": cat,
                              "contractLimit": round(rng.uniform(lo, hi), 1)})
    rels["CONNECTED_TO"].append((cid, rng.choice(sub_ids)))
    for _ in range(2 if i <= N_DOUBLE_METER else 1):
        mno += rng.randint(11, 97)
        mid = f"Meter_AMI{mno}"
        status = "несправний" if rng.random() < 0.08 else ("на повірці" if rng.random() < 0.04 else "активний")
        nodes["Meter"].append({"id": mid, "name": f"Лічильник AMI-{mno}", "status": status,
                               "meterType": "однофазний" if cat == "побутовий" else "трифазний"})
        rels["HAS_METER"].append((cid, mid))
        meters.append(mid)

days = [f"2026-09-{d:02d}" for d in range(11, 31)][:N_WEATHER_DAYS]
for d in days:
    wid = "WeatherCondition_" + d.replace("-", "")
    nodes["WeatherCondition"].append({"id": wid, "name": f"Погода {d}", "temperature": round(rng.uniform(-2, 18), 1),
                                      "cloudCover": rng.choice(["ясно", "мінлива", "суцільна"])})
meas_ids = []
for i in range(1, N_MEASUREMENTS + 1):
    xid = f"Measurement_{i:04d}"
    mid = meters[(i * 7) % len(meters)]
    d = days[i % len(days)]
    nodes["Measurement"].append({"id": xid, "name": f"Вимірювання №{i}",
                                 "consumptionValue": round(rng.uniform(1, 300), 1),
                                 "voltage": round(rng.uniform(200, 236), 1), "timestamp": f"{d}T{rng.choice(['08','12','18'])}:00:00"})
    rels["RECORDED"].append((mid, xid))
    rels["INFLUENCES"].append(("WeatherCondition_" + d.replace("-", ""), xid))
    meas_ids.append(xid)

MT = ["LSTM", "GRU", "VAR", "ARIMA", "LSTM", "GRU", "VAR", "LSTM"]
for i in range(1, N_MODELS + 1):
    fm = f"ForecastModel_{i}"
    nodes["ForecastModel"].append({"id": fm, "name": f"Модель {MT[i-1]} №{i}", "modelType": MT[i - 1],
                                   "accuracy": round(rng.uniform(75, 94), 1)})
    for x in sorted(rng.sample(meas_ids, 15)):
        rels["TRAINED_ON"].append((fm, x))
    for w in rng.sample([n["id"] for n in nodes["WeatherCondition"]], 2):
        rels["AFFECTS_MODEL"].append((w, fm))
for i in range(1, N_FORECASTS + 1):
    fid = f"Forecast_{i:03d}"
    fm = f"ForecastModel_{rng.randint(1, N_MODELS)}"
    sid = rng.choice([s for s in sub_ids if s in managed_by])
    nodes["Forecast"].append({"id": fid, "name": f"Прогноз №{i}", "errorPercentage": round(rng.uniform(2, 14), 1),
                              "forecastPeriod": rng.choice(["доба", "тиждень"])})
    rels["GENERATED"].append((fm, fid))
    rels["FORECAST_FOR"].append((fid, sid))
    rels["USES_FORECAST"].append((managed_by[sid], fid))

for lab, items in nodes.items():
    cols = list(items[0].keys())
    with (OUT / f"nodes_{lab.lower()}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(items)
for typ, pairs in rels.items():
    with (OUT / f"rels_{typ.lower()}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["start", "end"]); w.writerows(pairs)


CLASS = {"Consumer": "Consumer", "Meter": "Meter", "Measurement": "Measurement", "WeatherCondition": "WeatherCondition",
         "ForecastModel": "ForecastModel", "Forecast": "Forecast", "Dispatcher": "Dispatcher", "Substation": "Substation"}
SUBCLASS = {"побутовий": "ResidentialConsumer", "комерційний": "CommercialConsumer", "промисловий": "IndustrialConsumer"}
PROP = {"name": "skos:prefLabel", "category": ":consumerCategory", "status": ":meterStatus"}

RDFREL = {"HAS_METER": (":hasMeter", False), "CONNECTED_TO": (":connectedToSubstation", False),
          "RECORDED": (":measuredByMeter", True), "INFLUENCES": (":influencesMeasurement", False),
          "AFFECTS_MODEL": (":influencesModel", False), "TRAINED_ON": (":trainedOnMeasurement", False),
          "GENERATED": (":generatedByModel", True), "USES_FORECAST": (":usesForecast", False),
          "MANAGES": (":managedByDispatcher", True), "FEEDS": (":upstreamOf", False),
          "FORECAST_FOR": (":forecastForSubstation", False)}


def lit(v):
    if isinstance(v, float):
        return f'"{v}"^^xsd:double'
    if isinstance(v, int):
        return f'"{v}"^^xsd:integer'
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


lines = ["@prefix : <http://www.semanticweb.org/energy-forecasting#> .",
         "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
         "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
n_triples = 0
for lab, items in nodes.items():
    if lab == "Region":
        continue                     
    for n in items:
        types = [f":{CLASS[lab]}"]   
        if lab == "Consumer":
            types.append(f":{SUBCLASS[n['category']]}")
        lines.append(f":{n['id']} a {', '.join(types)} .")
        n_triples += len(types)
        for k, v in n.items():
            if k == "id":
                continue
            lines.append(f":{n['id']} {PROP.get(k, ':' + k)} {lit(v)} .")
            n_triples += 1
for typ, pairs in rels.items():
    if typ == "LOCATED_IN":
        continue
    pred, flip = RDFREL[typ]
    for a, b in pairs:
        s, o = (b, a) if flip else (a, b)
        lines.append(f":{s} {pred} :{o} .")
        n_triples += 1
(OUT / "bench.ttl").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("nodes:", {k: len(v) for k, v in nodes.items()}, "total", sum(len(v) for v in nodes.values()))
print("rels :", {k: len(v) for k, v in rels.items()}, "total", sum(len(v) for v in rels.values()))
print("RDF triples:", n_triples)
