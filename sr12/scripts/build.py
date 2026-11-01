"""Створює сховище за sql/ddl.sql, заповнює невеликим набором даних і виконує 5 запитів.

Дані: фактичне добове споживання підстанцій — агрегат сховища ЛР12 (data/source/actual_daily.csv);
моделі — граф ЛР9 (nodes_forecastmodel.csv); прогнози синтетичні: прогноз = факт × (1 + ε),
ε ~ N(зсув моделі; σ моделі × множник горизонту), seed 42. Вихід: data/sr12.duckdb, docs/queries_results.md.
"""
import csv, random
from datetime import date, timedelta
from pathlib import Path
import duckdb, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/source"
DB = ROOT / "data/sr12.duckdb"
NS = "http://www.semanticweb.org/energy-forecasting#"
START, END = date(2026, 1, 1), date(2026, 1, 31)
HORIZONS = {1: (1, "1 доба наперед"), 2: (7, "7 діб наперед")}
# версії моделей у січні 2026: (model_id, version, training_date, accuracy, valid_from, valid_to)
VERSIONS = [
    ("ForecastModel_VAR1", 1, "2025-11-01", 84.5, "2025-11-01", "9999-12-31"),
    ("ForecastModel_LSTM2", 1, "2025-06-20", 78.0, "2025-06-20", "9999-12-31"),
    ("ForecastModel_LSTM1", 1, "2025-10-01", 86.0, "2025-10-01", "2026-01-14"),   # синтетична попередня версія
    ("ForecastModel_LSTM1", 2, "2026-01-15", 92.0, "2026-01-15", "9999-12-31"),   # граф ЛР9: trainingDate 2026-01-15
]
# похибка, частка факту: (зсув, σ); VAR — гірше у вихідні
ERR = {("ForecastModel_VAR1", 1): (0.02, 0.06), ("ForecastModel_LSTM2", 1): (-0.04, 0.09),
       ("ForecastModel_LSTM1", 1): (0.00, 0.07), ("ForecastModel_LSTM1", 2): (0.00, 0.04)}


def main():
    rnd = random.Random(42)
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    con.execute((ROOT / "sql/ddl.sql").read_text(encoding="utf-8"))

    # виміри
    d0 = START - timedelta(days=7)
    con.execute(f"""INSERT INTO dim_date SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER), d, isodow(d), isodow(d) >= 6,
                    weekofyear(d), month(d), quarter(d), year(d)
                    FROM (SELECT CAST(unnest(generate_series(DATE '{d0}', DATE '{END}', INTERVAL 1 DAY)) AS DATE) d)""")
    con.executemany("INSERT INTO dim_horizon VALUES (?, ?, ?, 'короткостроковий прогноз')",
                    [(k, d, lbl) for k, (d, lbl) in HORIZONS.items()])
    cat = "Формалізовані (математичні) моделі"
    con.executemany("INSERT INTO dim_model_class VALUES (?, ?, ?, ?, ?, ?, ?)", [
        (0, NS + "ForecastModel", "Модель прогнозування", None, None, cat, 3),
        (1, NS + "StatisticalModel", "Статистична модель", NS + "ForecastModel", "Модель прогнозування", cat, 4),
        (2, NS + "MachineLearningModel", "Модель машинного навчання", NS + "ForecastModel", "Модель прогнозування", cat, 4)])
    nodes = {r["id"]: r for r in csv.DictReader(open(SRC / "nodes_forecastmodel.csv", encoding="utf-8"))}
    for k, (mid, ver, td, acc, vf, vt) in enumerate(VERSIONS, 1):
        n = nodes[mid]
        con.execute("INSERT INTO dim_model VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [k, mid, n["name"], n["modelType"], 1 if n["subLabel"] == "StatisticalModel" else 2,
                     ver, td, acc, vf, vt, vt == "9999-12-31"])
    con.execute(f"""INSERT INTO dim_substation SELECT row_number() OVER (), substation_id, substation_name,
                    nominal_capacity_kw, region_name FROM read_csv('{(SRC / 'substations.csv').as_posix()}')""")

    # факт: прогноз складається в день issue = target − горизонт версією моделі, чинною на дату складання
    actual = {(r["substation_id"], r["date"]): float(r["actual_kwh"])
              for r in csv.DictReader(open(SRC / "actual_daily.csv", encoding="utf-8"))}
    subs = dict(con.execute("SELECT substation_id, substation_key FROM dim_substation").fetchall())
    vers = con.execute("SELECT model_key, model_id, version, class_key, valid_from, valid_to FROM dim_model").fetchall()
    rows = []
    for (sid, ds), fact in sorted(actual.items()):
        t = date.fromisoformat(ds)
        for hk, (hd, _) in HORIZONS.items():
            issue = t - timedelta(days=hd)
            for mk, mid, ver, ck, vf, vt in vers:
                if not (vf <= issue <= vt):
                    continue
                bias, sd = ERR[(mid, ver)]
                sd *= 1.6 if hd == 7 else 1.0
                if mid == "ForecastModel_VAR1" and t.isoweekday() >= 6:
                    bias += 0.05
                f = round(fact * (1 + rnd.gauss(bias, sd)), 3)
                rows.append((int(t.strftime("%Y%m%d")), int(issue.strftime("%Y%m%d")), hk, mk, ck, subs[sid],
                             f, fact, round(f - fact, 3), round(abs(f - fact), 3), round(100 * abs(f - fact) / fact, 3), mid))
    df = pd.DataFrame(rows, columns=["target_date_key", "issue_date_key", "horizon_key", "model_key", "class_key",
                                     "substation_key", "forecast_kwh", "actual_kwh", "error_kwh", "abs_error_kwh",
                                     "ape_pct", "model_id"])
    df = df.sort_values(["model_id", "substation_key", "horizon_key", "target_date_key"])
    df["mtd_abs_error_kwh"] = df.groupby(["model_id", "substation_key", "horizon_key"])["abs_error_kwh"].cumsum().round(3)
    con.register("df", df.drop(columns="model_id"))
    con.execute("INSERT INTO fact_forecast SELECT * FROM df")

    checks = {
        "рядків факту": "SELECT count(*) FROM fact_forecast",
        "«сироти» (усі 6 FK)": """SELECT count(*) FROM fact_forecast f
            LEFT JOIN dim_date t ON t.date_key = f.target_date_key LEFT JOIN dim_date i ON i.date_key = f.issue_date_key
            LEFT JOIN dim_horizon h USING (horizon_key) LEFT JOIN dim_model m USING (model_key)
            LEFT JOIN dim_model_class k ON k.class_key = f.class_key LEFT JOIN dim_substation s USING (substation_key)
            WHERE t.date_key IS NULL OR i.date_key IS NULL OR h.horizon_key IS NULL OR m.model_key IS NULL
               OR k.class_key IS NULL OR s.substation_key IS NULL""",
        "дата складання ≠ цільова − горизонт": """SELECT count(*) FROM fact_forecast f JOIN dim_date t ON t.date_key = f.target_date_key
            JOIN dim_date i ON i.date_key = f.issue_date_key JOIN dim_horizon h USING (horizon_key)
            WHERE i.date <> t.date - h.horizon_days""",
        "прогноз складено версією, не чинною на дату складання": """SELECT count(*) FROM fact_forecast f
            JOIN dim_date i ON i.date_key = f.issue_date_key JOIN dim_model m USING (model_key)
            WHERE i.date NOT BETWEEN m.valid_from AND m.valid_to""",
    }
    out = ["# Перевірка схеми й 5 запитів (СР12)", "", "| Перевірка | Значення |", "|---|---|"]
    for name, sql in checks.items():
        v = con.execute(sql).fetchall()[0][0]
        out.append(f"| {name} | {v} |")
        print(f"{name}: {v}")
    for f in sorted((ROOT / "sql/queries").glob("q*.sql")):
        sql = f.read_text(encoding="utf-8")
        res = con.sql(sql).df()
        q = next(l.split(":", 1)[1].strip() for l in sql.splitlines() if l.startswith("-- Питання"))
        out += ["", f"## {f.stem}", "", f"**Питання.** {q}", "", "```sql",
                "\n".join(l for l in sql.splitlines() if not l.startswith("--")).strip(), "```", "",
                res.to_markdown(index=False)]
        print(f"\n== {f.stem}\n{res.to_string(index=False)}")
    (ROOT / "docs/queries_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    con.close()


if __name__ == "__main__":
    main()
