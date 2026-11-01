import csv, math, random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
START, DAYS = date(2026, 1, 1), 31
ROOT = Path(__file__).resolve().parents[1]
SRC, RAW = ROOT / "data/source", ROOT / "data/raw"

# частка договірного ліміту за годиною: (будній день, вихідний)
def profile(cls: str, h: int, weekend: bool) -> float:
    if cls == "Residential":
        p = 0.15 if h < 6 else 0.45 if h < 10 else 0.30 if h < 18 else 0.60 if h < 23 else 0.20
        return p * (1.15 if weekend and 10 <= h < 18 else 1.0)
    if cls == "Commercial":
        if weekend:
            return 0.25 if 9 <= h < 18 else 0.10
        return 0.55 if 8 <= h < 19 else 0.12
    # Industrial: дві зміни 06–22 у будні
    if weekend:
        return 0.25
    return 0.60 if 6 <= h < 22 else 0.30

HEAT = {"Residential": 0.025, "Commercial": 0.020, "Industrial": 0.005}  # +частка на 1 °C нижче +5 °C
REGION_OFFSET = {"Region_Lviv": 0.0, "Region_Zakarpattia": 3.0, "Region_IvanoFrankivsk": -1.0,
                 "Region_Ternopil": -1.5, "Region_Rivne": -1.0, "Region_Volyn": -0.5}
CONTRACT_CHANGES = [("Consumer_3310", "2026-01-16", 150.0)]  # підвищення ліміту → SCD 2
LOAD_BOOST = {"Consumer_3310": 1.6}  # споживач, що до зміни ліміту його перевищував


def read(name):
    with open(SRC / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    rnd = random.Random(SEED)
    consumers = {r["id"]: r for r in read("nodes_consumer.csv")}
    meters = {r["id"]: r for r in read("nodes_meter.csv")}
    has_meter = read("rels_has_meter.csv")
    conn = {r["start"]: r["end"] for r in read("rels_connected_to.csv")}
    region = {r["start"]: r["end"] for r in read("rels_located_in.csv")}
    anchors = {r["id"][-8:]: float(r["temperature"]) for r in read("nodes_weathercondition.csv")}

    # 1) погода: денна середня для Львівщини (випадкове блукання + опорні дні графа)
    lviv, t = [], -4.0
    for d in range(DAYS):
        day = START + timedelta(d)
        t = max(-18.0, min(4.0, t + rnd.gauss(0, 2.0)))
        t = anchors.get(day.strftime("%Y%m%d"), t)
        lviv.append(t)
    weather = {}
    for reg, off in REGION_OFFSET.items():
        for d in range(DAYS):
            mean = lviv[d] + off + rnd.gauss(0, 0.7)
            for h in range(24):
                weather[(reg, d, h)] = round(mean + 3 * math.sin((h - 8) * math.pi / 12), 1)

    # 2) показання
    limits = {c: float(r["contractLimit"]) for c, r in consumers.items()}
    n_meters = {}
    for r in has_meter:
        n_meters[r["start"]] = n_meters.get(r["start"], 0) + 1
    rows = []
    for rel in sorted(has_meter, key=lambda r: r["end"]):
        cid, mid = rel["start"], rel["end"]
        cls, reg = consumers[cid]["subLabel"], region[conn[cid]]
        status = meters[mid]["status"]
        stop_day = rnd.randint(19, 27) if status == "несправний" else DAYS
        gap = range(13, 17) if status == "на повірці" else range(0)
        register = round(rnd.uniform(10_000, 90_000), 1)
        for d in range(DAYS):
            day = START + timedelta(d)
            weekend = day.isoweekday() >= 6
            for h in range(24):
                noise = max(0.0, rnd.gauss(1.0, 0.08))
                if d >= stop_day or d in gap:
                    continue
                temp = weather[(reg, d, h)]
                heat = 1 + HEAT[cls] * max(0.0, 5 - temp)
                boost = LOAD_BOOST.get(cid, 1.0)
                load_kw = limits[cid] * profile(cls, h, weekend) * heat * noise * boost
                energy = round(load_kw / n_meters[cid], 3)
                register = round(register + energy, 3)
                volt = round(rnd.gauss(230, 2.5) - 6 * load_kw / limits[cid], 1)
                ts = datetime(day.year, day.month, day.day, h)
                rows.append((mid, ts.isoformat(), energy, register, volt))

    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "readings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["meter_id", "ts", "energy_kwh", "register_kwh", "voltage_v"])
        w.writerows(rows)
    with open(RAW / "weather.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region_id", "ts", "temperature_c"])
        for (reg, d, h), v in sorted(weather.items()):
            day = START + timedelta(d)
            w.writerow([reg, datetime(day.year, day.month, day.day, h).isoformat(), v])
    with open(RAW / "contract_changes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["consumer_id", "valid_from", "contract_limit_kw"])
        w.writerows(CONTRACT_CHANGES)
    total = sum(r[2] for r in rows)
    print(f"readings: {len(rows)} рядків, лічильників {len({r[0] for r in rows})}, "
          f"сума energy_kwh = {total:,.3f}; weather: {len(weather)} рядків")


if __name__ == "__main__":
    main()
