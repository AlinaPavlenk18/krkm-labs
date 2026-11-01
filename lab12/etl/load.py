"""ЛР12 · ELT: сирі CSV → staging у DuckDB → виміри й факт (SQL) → перевірки якості → Parquet."""
import json, datetime
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/warehouse.duckdb"
VERSION = "1.0.0"
NS = "http://www.semanticweb.org/energy-forecasting#"
CAT, DOM = "Суб''єкти енергосистеми", "Прогнозування енергоспоживання"  # рівні 2 і 1 таксономії ЛР4
S = (ROOT / "data/source").as_posix()
R = (ROOT / "data/raw").as_posix()

TRANSFORM = f"""
-- staging (E + L)
CREATE TABLE stg_readings AS SELECT * FROM read_csv('{R}/readings.csv', header=true, timestampformat='%Y-%m-%dT%H:%M:%S');
CREATE TABLE stg_weather  AS SELECT * FROM read_csv('{R}/weather.csv',  header=true, timestampformat='%Y-%m-%dT%H:%M:%S');
CREATE TABLE stg_changes  AS SELECT * FROM read_csv('{R}/contract_changes.csv', header=true);

-- T: виміри
INSERT INTO dim_date
SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER), d, day(d), isodow(d),
       ['Пн','Вт','Ср','Чт','Пт','Сб','Нд'][isodow(d)], isodow(d) >= 6, weekofyear(d), month(d),
       ['січень','лютий','березень','квітень','травень','червень','липень','серпень',
        'вересень','жовтень','листопад','грудень'][month(d)], quarter(d), year(d)
FROM (SELECT CAST(unnest(generate_series(min(ts)::DATE, max(ts)::DATE, INTERVAL 1 DAY)) AS DATE) AS d
      FROM stg_readings);

INSERT INTO dim_hour
SELECT h, lpad(CAST(h AS VARCHAR), 2, '0') || ':00',
       CASE WHEN h < 6 THEN 'ніч' WHEN h < 12 THEN 'ранок' WHEN h < 18 THEN 'день' ELSE 'вечір' END,
       h BETWEEN 8 AND 10 OR h BETWEEN 18 AND 21
FROM range(24) t(h);

INSERT INTO dim_consumer_class VALUES
 (0, '{NS}Consumer',            'Споживач',             NULL,           NULL,       '{CAT}', '{DOM}', 3),
 (1, '{NS}ResidentialConsumer', 'Побутовий споживач',   '{NS}Consumer', 'Споживач', '{CAT}', '{DOM}', 4),
 (2, '{NS}CommercialConsumer',  'Комерційний споживач', '{NS}Consumer', 'Споживач', '{CAT}', '{DOM}', 4),
 (3, '{NS}IndustrialConsumer',  'Промисловий споживач', '{NS}Consumer', 'Споживач', '{CAT}', '{DOM}', 4);

INSERT INTO dim_substation
SELECT row_number() OVER (ORDER BY CAST(split_part(s.id, '_', 2) AS INTEGER)), s.id, s.name,
       s.nominalCapacity, r.id, r.name
FROM read_csv('{S}/nodes_substation.csv', header=true) s
JOIN read_csv('{S}/rels_located_in.csv', header=true) l ON l.start = s.id
JOIN read_csv('{S}/nodes_region.csv', header=true) r ON r.id = l."end";

-- SCD 2: базова версія з графа ЛР9 + зміни ліміту
INSERT INTO dim_consumer
WITH base AS (
  SELECT id AS consumer_id, name AS consumer_name, subLabel, DATE '2026-01-01' AS valid_from,
         contractLimit AS contract_limit_kw
  FROM read_csv('{S}/nodes_consumer.csv', header=true)),
versions AS (
  SELECT consumer_id, consumer_name, subLabel, valid_from, contract_limit_kw FROM base
  UNION ALL
  SELECT c.consumer_id, b.consumer_name, b.subLabel, c.valid_from, c.contract_limit_kw
  FROM stg_changes c JOIN base b USING (consumer_id))
SELECT row_number() OVER (ORDER BY consumer_id, valid_from), consumer_id, consumer_name,
       CASE subLabel WHEN 'Residential' THEN 1 WHEN 'Commercial' THEN 2 ELSE 3 END,
       contract_limit_kw, valid_from,
       coalesce(lead(valid_from) OVER w - INTERVAL 1 DAY, DATE '9999-12-31'),
       lead(valid_from) OVER w IS NULL
FROM versions WINDOW w AS (PARTITION BY consumer_id ORDER BY valid_from);

-- T: факт (зерно — лічильник × година)
INSERT INTO fact_consumption
SELECT CAST(strftime(r.ts, '%Y%m%d') AS INTEGER), hour(r.ts), c.consumer_key, c.class_key,
       s.substation_key, r.meter_id, r.energy_kwh, r.register_kwh, r.voltage_v, w.temperature_c
FROM stg_readings r
JOIN read_csv('{S}/rels_has_meter.csv', header=true) hm ON hm."end" = r.meter_id
JOIN dim_consumer c ON c.consumer_id = hm.start AND r.ts::DATE BETWEEN c.valid_from AND c.valid_to
JOIN read_csv('{S}/rels_connected_to.csv', header=true) ct ON ct.start = hm.start
JOIN dim_substation s ON s.substation_id = ct."end"
JOIN stg_weather w ON w.region_id = s.region_id AND w.ts = r.ts;
"""

# (назва, тип, SQL → число порушень; для 'warn' — показник)
CHECKS = [
    ("Немає «сиріт»: факт → dim_date", "orphans",
     "SELECT count(*) FROM fact_consumption f LEFT JOIN dim_date d USING (date_key) WHERE d.date_key IS NULL"),
    ("Немає «сиріт»: факт → dim_hour", "orphans",
     "SELECT count(*) FROM fact_consumption f LEFT JOIN dim_hour d USING (hour_key) WHERE d.hour_key IS NULL"),
    ("Немає «сиріт»: факт → dim_consumer", "orphans",
     "SELECT count(*) FROM fact_consumption f LEFT JOIN dim_consumer d USING (consumer_key) WHERE d.consumer_key IS NULL"),
    ("Немає «сиріт»: факт → dim_consumer_class", "orphans",
     "SELECT count(*) FROM fact_consumption f LEFT JOIN dim_consumer_class d USING (class_key) WHERE d.class_key IS NULL"),
    ("Немає «сиріт»: факт → dim_substation", "orphans",
     "SELECT count(*) FROM fact_consumption f LEFT JOIN dim_substation d USING (substation_key) WHERE d.substation_key IS NULL"),
    ("Без втрат під час T: рядків факту = рядків staging", "completeness",
     "SELECT abs((SELECT count(*) FROM stg_readings) - (SELECT count(*) FROM fact_consumption))"),
    ("NOT NULL: міри й ключі факту", "not_null",
     "SELECT count(*) FROM fact_consumption WHERE energy_kwh IS NULL OR register_kwh IS NULL "
     "OR voltage_v IS NULL OR temperature_c IS NULL OR meter_id IS NULL"),
    ("Унікальність зерна (meter_id, date_key, hour_key)", "unique",
     "SELECT count(*) - count(DISTINCT (meter_id, date_key, hour_key)) FROM fact_consumption"),
    ("Діапазон: energy_kwh ≥ 0", "range",
     "SELECT count(*) FROM fact_consumption WHERE energy_kwh < 0"),
    ("Діапазон: напруга 207–253 В (230 В ± 10 %)", "range",
     "SELECT count(*) FROM fact_consumption WHERE voltage_v NOT BETWEEN 207 AND 253"),
    ("Діапазон: температура −40…+40 °C", "range",
     "SELECT count(*) FROM fact_consumption WHERE temperature_c NOT BETWEEN -40 AND 40"),
    ("Регістр лічильника не спадає в часі", "monotonic",
     "SELECT count(*) FROM (SELECT register_kwh - lag(register_kwh) OVER "
     "(PARTITION BY meter_id ORDER BY date_key, hour_key) AS dlt FROM fact_consumption) WHERE dlt < 0"),
    ("SCD 2: одна поточна версія на споживача, без перекриттів", "scd2",
     "SELECT (SELECT count(*) FROM (SELECT consumer_id FROM dim_consumer GROUP BY consumer_id "
     "HAVING sum(CASE WHEN is_current THEN 1 ELSE 0 END) <> 1)) + (SELECT count(*) FROM dim_consumer a "
     "JOIN dim_consumer b ON a.consumer_id = b.consumer_id AND a.consumer_key < b.consumer_key "
     "AND a.valid_from <= b.valid_to AND b.valid_from <= a.valid_to)"),
    ("Повнота годин, % від очікуваних (попередження, поріг 95 %)", "warn",
     "SELECT round(100.0 * count(*) / ((SELECT count(DISTINCT meter_id) FROM stg_readings) * "
     "(SELECT count(*) FROM dim_date) * 24), 2) FROM fact_consumption"),
]


def main():
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    con.execute((ROOT / "sql/ddl.sql").read_text(encoding="utf-8"))
    con.execute(TRANSFORM)

    results, ok_all = [], True
    for name, kind, sql in CHECKS:
        v = con.execute(sql).fetchone()[0]
        ok = (v >= 95) if kind == "warn" else (v == 0)
        ok_all &= ok
        results.append({"check": name, "type": kind, "value": float(v), "passed": bool(ok)})

    tables = ["dim_date", "dim_hour", "dim_consumer_class", "dim_substation", "dim_consumer", "fact_consumption"]
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    for t in tables:
        con.execute(f"COPY {t} TO '{(ROOT / 'data' / (t + '.parquet')).as_posix()}' (FORMAT parquet)")
    for t in ["stg_readings", "stg_weather", "stg_changes"]:
        con.execute(f"DROP TABLE {t}")
    total = con.execute("SELECT round(sum(energy_kwh), 3) FROM fact_consumption").fetchone()[0]
    con.close()

    manifest = {"dataset_version": VERSION, "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "generator": "etl/generate.py (seed 42, період 2026-01-01…2026-01-31)",
                "source": "граф ЛР9 (data/source/*.csv) + синтетичні показання",
                "duckdb": duckdb.__version__, "row_counts": counts, "sum_energy_kwh": total,
                "quality_passed": ok_all}
    (ROOT / "data/VERSION.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "data/quality_report.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# Звіт про якість даних (версія набору {VERSION})", "",
          f"DuckDB {duckdb.__version__}; рядків факту: {counts['fact_consumption']}; "
          f"сума energy_kwh: {total}", "",
          "| № | Перевірка | Тип | Значення | Результат |", "|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        md.append(f"| {i} | {r['check']} | {r['type']} | {r['value']:g} | {'пройдено' if r['passed'] else 'НЕ пройдено'} |")
    (ROOT / "docs/quality_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps(counts, ensure_ascii=False))
    for r in results:
        print(f"{'OK ' if r['passed'] else 'FAIL'}  {r['check']}: {r['value']:g}")
    print(f"Версія набору {VERSION}; сума energy_kwh = {total}; усі перевірки: {ok_all}")


if __name__ == "__main__":
    main()
