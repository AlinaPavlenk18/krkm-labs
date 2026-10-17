#!/usr/bin/env python3
"""
Формує data/triples_final.csv для ЛР9.

Джерела:
  1) data/source/lab08_data.ttl — ABox з ЛР8 (25 індивідів, 148 триплетів), source = "lab08:data.ttl";
  2) синтетичне розширення (детермінований генератор, SEED = 42), source = "synthetic:gen_v1(seed=42)".
     Синтетичні індивіди НЕ є реальними об'єктами енергомережі — це навчальний набір даних,
     згенерований за правилами словника ЛР8 (домени/кодомени, кардинальності).

Колонки CSV:
  subject, predicate, object, object_type (iri|literal), datatype, lang,
  source, confidence, valid_from
Колонки source/confidence/valid_from — провенанс твердження; для об'єктних
властивостей вони переходять у властивості зв'язків графа (Результат 1, крок 3).
"""
import csv
import random
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

SEED = 42
EF = "http://www.semanticweb.org/energy-forecasting#"
ROOT = Path(__file__).resolve().parents[1]
SRC_TTL = ROOT / "data" / "source" / "lab08_data.ttl"
OUT = ROOT / "data" / "triples_final.csv"

LAB08 = "lab08:data.ttl"
SYN = "synthetic:gen_v1(seed=42)"

rng = random.Random(SEED)
rows = []


def add(s, p, o, kind="iri", dt="", lang="", source=SYN, conf="", vf=""):
    rows.append(dict(subject=s, predicate=p, object=str(o), object_type=kind,
                     datatype=dt, lang=lang, source=source,
                     confidence=conf, valid_from=vf))


def lit(s, p, v, dt="string", source=SYN):
    add(s, p, v, kind="literal", dt=dt, source=source)


def label(s, text, source=SYN):
    add(s, "skos:prefLabel", text, kind="literal", lang="uk", source=source)


def rel(s, p, o, conf="1.0", vf="", source=SYN):
    add(s, p, o, kind="iri", source=source, conf=conf, vf=vf)

g = Graph()
g.parse(SRC_TTL, format="turtle")


def short(term):
    t = str(term)
    if t.startswith(EF):
        return t[len(EF):]
    if t == str(RDF.type):
        return "rdf:type"
    if t == str(SKOS.prefLabel):
        return "skos:prefLabel"
    return t


LAB08_VF = "2026-09-24"
for s, p, o in sorted(g):
    S, P = short(s), short(p)
    if isinstance(o, URIRef):
        O = short(o)
        if P == "rdf:type":
            add(S, P, O, kind="iri", source=LAB08)
        else:
            add(S, P, O, kind="iri", source=LAB08, conf="1.0", vf=LAB08_VF)
    else:
        assert isinstance(o, Literal)
        dt = short(o.datatype).replace(str(XSD), "") if o.datatype else ("" if o.language else "string")
        if o.datatype:
            dt = str(o.datatype).replace(str(XSD), "")
        add(S, P, str(o), kind="literal", dt=dt, lang=o.language or "", source=LAB08)

n_lab08 = len(rows)

CITY = {
    "Львівська область": "м. Львів",
    "Волинська область": "м. Луцьк",
    "Закарпатська область": "м. Ужгород",
    "Тернопільська область": "м. Тернопіль",
    "Рівненська область": "м. Рівне",
    "Івано-Франківська область": "м. Івано-Франківськ",
}
STREETS = ["вул. Незалежності", "вул. Січових Стрільців", "вул. Грушевського", "вул. Франка",
           "вул. Лесі Українки", "вул. Наукова", "вул. Зелена", "вул. Городоцька", "вул. Соборна",
           "вул. Заводська", "вул. Привокзальна", "вул. Садова"]

new_subs = [
    ("Substation_1", "Львівська область", 2500.0, 1850.0),   
    ("Substation_2", "Волинська область", 800.0, 512.0),
    ("Substation_3", "Рівненська область", 600.0, 402.0),
    ("Substation_4", "Тернопільська область", 500.0, 450.0),  
    ("Substation_6", "Івано-Франківська область", 400.0, 236.0),
    ("Substation_8", "Закарпатська область", 300.0, 141.0),
    ("Substation_10", "Львівська область", 1200.0, 780.0),
    ("Substation_11", "Рівненська область", 350.0, 301.0),  
]
for sid, reg, cap, load in new_subs:
    add(sid, "rdf:type", "Substation")
    label(sid, f"Підстанція №{sid.split('_')[1]}")
    lit(sid, "region", reg)
    lit(sid, "nominalCapacity", cap, "double")
    lit(sid, "currentLoad", load, "double")

SUB_REGION = {sid: reg for sid, reg, _, _ in new_subs}
SUB_REGION.update({"Substation_7": "Львівська область", "Substation_5": "Волинська область",
                   "Substation_12": "Львівська область", "Substation_9": "Закарпатська область"})

for a, b, vf in [("Substation_1", "Substation_7", "2019-05-01"),
                 ("Substation_1", "Substation_10", "2019-05-01"),
                 ("Substation_1", "Substation_2", "2020-03-15"),
                 ("Substation_10", "Substation_4", "2021-07-01"),
                 ("Substation_4", "Substation_6", "2021-07-01"),
                 ("Substation_2", "Substation_3", "2020-03-15"),
                 ("Substation_3", "Substation_11", "2022-10-10"),
                 ("Substation_9", "Substation_8", "2023-02-01")]:
    rel(a, "upstreamOf", b, vf=vf)

for did, q, sh in [("Dispatcher_4", "старший", "ранкова"),
                   ("Dispatcher_5", "провідний", "вечірня"),
                   ("Dispatcher_6", "молодший", "нічна")]:
    add(did, "rdf:type", "Dispatcher")
    label(did, f"Диспетчер №{did.split('_')[1]} ({q})")
    lit(did, "qualification", q)
    lit(did, "shift", sh)
for sub, d, vf in [("Substation_1", "Dispatcher_4", "2025-01-01"),
                   ("Substation_10", "Dispatcher_4", "2025-01-01"),
                   ("Substation_2", "Dispatcher_5", "2025-03-01"),
                   ("Substation_3", "Dispatcher_5", "2025-03-01"),
                   ("Substation_8", "Dispatcher_5", "2025-06-01"),
                   ("Substation_4", "Dispatcher_6", "2025-09-01"),
                   ("Substation_6", "Dispatcher_6", "2025-09-01"),
                   ("Substation_11", "Dispatcher_2", "2026-02-01")]:
    rel(sub, "managedByDispatcher", d, vf=vf)

CLASS = {"побутовий": "ResidentialConsumer", "комерційний": "CommercialConsumer",
         "промисловий": "IndustrialConsumer"}
LIMIT = {"побутовий": (5.0, 15.0), "комерційний": (40.0, 200.0), "промисловий": (250.0, 900.0)}
categories = ["побутовий"] * 22 + ["комерційний"] * 10 + ["промисловий"] * 5
rng.shuffle(categories)
serving_subs = ["Substation_2", "Substation_3", "Substation_4", "Substation_6", "Substation_8",
                "Substation_10", "Substation_11", "Substation_12", "Substation_5", "Substation_7",
                "Substation_9"]
consumers = []
for i, cat in enumerate(categories):
    cid = f"Consumer_{5001 + i}"
    sub = serving_subs[i % len(serving_subs)]
    lo, hi = LIMIT[cat]
    add(cid, "rdf:type", CLASS[cat])
    label(cid, f"Споживач №{5001 + i} ({cat})")
    lit(cid, "consumerCategory", cat)
    lit(cid, "contractLimit", round(rng.uniform(lo, hi), 1), "double")
    lit(cid, "address", f"{CITY[SUB_REGION[sub]]}, {rng.choice(STREETS)}, {rng.randint(1, 120)}")
    year = rng.randint(2015, 2025)
    rel(cid, "connectedToSubstation", sub, vf=f"{year}-{rng.randint(1, 12):02d}-01")
    consumers.append((cid, cat, sub, year))

add("Consumer_5038", "rdf:type", "IndustrialConsumer")
label("Consumer_5038", "Споживач №5038 (промисловий)")
lit("Consumer_5038", "consumerCategory", "промисловий")
lit("Consumer_5038", "contractLimit", 1500.0, "double")
lit("Consumer_5038", "address", "м. Львів, вул. Промислова, 2")
rel("Consumer_5038", "connectedToSubstation", "Substation_1", vf="2018-01-01")
consumers.append(("Consumer_5038", "промисловий", "Substation_1", 2018))

meters = []
meter_no = 20000
statuses = (["активний"] * 34) + ["несправний"] * 4 + ["на повірці"] * 2
rng.shuffle(statuses)
st_iter = iter(statuses)
for cid, cat, sub, year in consumers:
    n_m = 2 if cid == "Consumer_5038" else 1  
    for _ in range(n_m):
        meter_no += rng.randint(137, 2900)
        mid = f"Meter_AMI{meter_no}"
        status = next(st_iter)
        mtype = "однофазний" if cat == "побутовий" else "трифазний"
        add(mid, "rdf:type", "Meter")
        label(mid, f"Лічильник AMI-{meter_no}")
        lit(mid, "meterStatus", status)
        lit(mid, "meterType", mtype)
        lit(mid, "readingInterval", 60 if cat == "побутовий" else rng.choice([15, 30]), "integer")
        rel(cid, "hasMeter", mid, vf=f"{max(year, 2020)}-{rng.randint(1, 12):02d}-15")
        meters.append((mid, cid, status, sub, cat))

meter_no += 911
mid = f"Meter_AMI{meter_no}"
add(mid, "rdf:type", "Meter")
label(mid, f"Лічильник AMI-{meter_no} (резервний)")
lit(mid, "meterStatus", "активний")
lit(mid, "meterType", "трифазний")
lit(mid, "readingInterval", 15, "integer")
rel("Consumer_4521", "hasMeter", mid, vf="2024-04-15")
meters.append((mid, "Consumer_4521", "активний", "Substation_7", "промисловий"))

weather = [("WeatherCondition_20260926", "2026-09-26", 4.0, "ясно"),
           ("WeatherCondition_20260927", "2026-09-27", 1.5, "мінлива"),
           ("WeatherCondition_20260928", "2026-09-28", -1.0, "суцільна"),
           ("WeatherCondition_20260929", "2026-09-29", 2.0, "мінлива"),
           ("WeatherCondition_20260930", "2026-09-30", 6.5, "ясно"),
           ("WeatherCondition_20260111", "2026-01-11", -15.5, "суцільна"),
           ("WeatherCondition_20260112", "2026-01-12", -9.0, "мінлива")]
for wid, d, t, cc in weather:
    add(wid, "rdf:type", "WeatherCondition")
    dd = d.split("-")
    label(wid, f"Погода {dd[2]}.{dd[1]}.{dd[0]}")
    lit(wid, "temperature", t, "double")
    lit(wid, "cloudCover", cc)
DATES = [w[1] for w in weather]

new_meas = []
meas_targets = [m for m in meters] + [meters[k] for k in (0, 5, 11, 17, 23)]
for k, (mid, cid, status, sub, cat) in enumerate(meas_targets[:45]):
    msid = f"Measurement_{4 + k:03d}"
    d = DATES[k % len(DATES)]
    base = {"побутовий": 6.0, "комерційний": 40.0, "промисловий": 180.0}[cat]
    val = round(base * rng.uniform(0.6, 1.5), 1)
    volt = round(rng.uniform(219.0, 236.0), 1) if status == "активний" else round(rng.uniform(196.0, 210.0), 1)
    add(msid, "rdf:type", "Measurement")
    label(msid, f"Вимірювання №{4 + k:03d}")
    lit(msid, "consumptionValue", val, "double")
    lit(msid, "voltage", volt, "double")
    lit(msid, "timestamp", f"{d}T{rng.choice(['08', '12', '18', '21'])}:00:00", "dateTime")
    rel(msid, "measuredByMeter", mid, vf=d)
    new_meas.append((msid, d))
    wid = "WeatherCondition_" + d.replace("-", "")
    rel(wid, "influencesMeasurement", msid, conf=f"{rng.uniform(0.6, 0.95):.2f}", vf=d)


models = [("ForecastModel_LSTM3", "MachineLearningModel", "LSTM", 89.0, "2026-08-30"),
          ("ForecastModel_ARIMA1", "StatisticalModel", "ARIMA", 81.0, "2026-02-10"),
          ("ForecastModel_GRU1", "MachineLearningModel", "GRU", 90.5, "2026-09-01")]
for mid, cls, mt, acc, td in models:
    add(mid, "rdf:type", cls)
    label(mid, f"Модель {mt} №{mid[-1]}")
    lit(mid, "modelType", mt)
    lit(mid, "accuracy", acc, "double")
    lit(mid, "trainingDate", td, "date")

autumn = [m for m, d in new_meas if d.startswith("2026-09")]
winter = [m for m, d in new_meas if d.startswith("2026-01")]
train_plan = {
    "ForecastModel_LSTM1": rng.sample(autumn, 5),
    "ForecastModel_VAR1": rng.sample(autumn, 4),
    "ForecastModel_LSTM2": rng.sample(winter, 4),      
    "ForecastModel_LSTM3": rng.sample(autumn, 7),
    "ForecastModel_ARIMA1": rng.sample(winter, 3) + rng.sample(autumn, 3),
    "ForecastModel_GRU1": rng.sample(autumn, 8),
}
for model, ms in train_plan.items():
    for m in sorted(ms):
        rel(model, "trainedOnMeasurement", m, vf="2026-09-30" if model != "ForecastModel_LSTM2" else "2025-06-20")

for wid, model in [("WeatherCondition_20260926", "ForecastModel_LSTM3"),
                   ("WeatherCondition_20260928", "ForecastModel_GRU1"),
                   ("WeatherCondition_20260929", "ForecastModel_LSTM3"),
                   ("WeatherCondition_20260111", "ForecastModel_ARIMA1"),
                   ("WeatherCondition_20260112", "ForecastModel_LSTM2"),
                   ("WeatherCondition_20260930", "ForecastModel_GRU1"),
                   ("WeatherCondition_20260927", "ForecastModel_VAR1")]:
    rel(wid, "influencesModel", model, conf=f"{rng.uniform(0.55, 0.85):.2f}", vf="2026-09-30")

SUB_DISP = {"Substation_7": "Dispatcher_1", "Substation_12": "Dispatcher_2", "Substation_5": "Dispatcher_3",
            "Substation_1": "Dispatcher_4", "Substation_10": "Dispatcher_4", "Substation_2": "Dispatcher_5",
            "Substation_3": "Dispatcher_5", "Substation_8": "Dispatcher_5", "Substation_4": "Dispatcher_6",
            "Substation_6": "Dispatcher_6", "Substation_11": "Dispatcher_2"}

for f, s in [("Forecast_20260924", "Substation_7"), ("Forecast_20260925", "Substation_12"),
             ("Forecast_20260110", "Substation_5")]:
    rel(f, "forecastForSubstation", s, conf="0.95", vf=f"2026-{f[13:15]}-{f[15:17]}")

fc_plan = [  
    ("2026-10-01", "ForecastModel_GRU1", "Substation_1", 3.2, "доба"),
    ("2026-10-01", "ForecastModel_LSTM3", "Substation_10", 4.1, "доба"),
    ("2026-10-02", "ForecastModel_LSTM1", "Substation_7", 5.0, "доба"),
    ("2026-10-02", "ForecastModel_VAR1", "Substation_2", 6.8, "доба"),
    ("2026-10-03", "ForecastModel_ARIMA1", "Substation_3", 8.9, "тиждень"),
    ("2026-10-03", "ForecastModel_GRU1", "Substation_4", 2.9, "доба"),
    ("2026-10-04", "ForecastModel_LSTM3", "Substation_6", 4.7, "доба"),
    ("2026-10-04", "ForecastModel_LSTM2", "Substation_11", 12.3, "доба"),
    ("2026-10-05", "ForecastModel_ARIMA1", "Substation_8", 9.6, "тиждень"),
    ("2026-10-05", "ForecastModel_GRU1", "Substation_5", 3.5, "доба"),
    ("2026-10-06", "ForecastModel_LSTM2", "Substation_12", 10.4, "доба"),
    ("2026-10-06", "ForecastModel_VAR1", "Substation_11", 7.2, "тиждень"),
    ("2026-10-07", "ForecastModel_LSTM3", "Substation_1", 3.9, "тиждень"),
    ("2026-10-07", "ForecastModel_LSTM1", "Substation_10", 4.4, "доба"),
    ("2026-10-08", "ForecastModel_GRU1", "Substation_2", 3.1, "доба"),
]
used = {}
for d, model, sub, err, per in fc_plan:
    base = "Forecast_" + d.replace("-", "")
    used[base] = used.get(base, 0) + 1
    fid = f"{base}_{used[base]}"
    add(fid, "rdf:type", "Forecast")
    dd = d.split("-")
    label(fid, f"Прогноз на {dd[2]}.{dd[1]}.{dd[0]} ({sub.replace('Substation_', 'ПС №')})")
    lit(fid, "forecastPeriod", per)
    lit(fid, "errorPercentage", err, "double")
    lit(fid, "predictedConsumption", round(rng.uniform(150, 2600), 1), "double")
    rel(fid, "generatedByModel", model, vf=d)
    rel(fid, "forecastForSubstation", sub, conf="0.95", vf=d)
    rel(SUB_DISP[sub], "usesForecast", fid, vf=d)

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

subjects = {r["subject"] for r in rows}
print(f"triples total: {len(rows)}  (lab08: {n_lab08}, synthetic: {len(rows) - n_lab08})")
print(f"distinct subjects: {len(subjects)}")
