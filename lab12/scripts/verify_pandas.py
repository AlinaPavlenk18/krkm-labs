"""Незалежна перевірка двох OLAP-результатів у pandas (лише Parquet-файли, без DuckDB).

1) q01 ROLLUP: енергія за підкласами таксономії та загальна сума.
2) q07 віконні: накопичене споживання та ковзне середнє за 7 днів.
"""
from pathlib import Path
import pandas as pd
import duckdb

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
fact = pd.read_parquet(D / "fact_consumption.parquet")
cls = pd.read_parquet(D / "dim_consumer_class.parquet")
dates = pd.read_parquet(D / "dim_date.parquet")
con = duckdb.connect(str(D / "warehouse.duckdb"), read_only=True)
sql = lambda name: con.sql((ROOT / "sql/olap" / name).read_text(encoding="utf-8")).df()
ok_all = True

# 1) ROLLUP за таксономією
p1 = (fact.merge(cls, on="class_key").groupby("class_label")["energy_kwh"].sum() / 1000).round(2)
p1_total = round(fact["energy_kwh"].sum() / 1000, 2)
q1 = sql("q01_rollup_taxonomy.sql")
q1_sub = q1[q1["підклас"] != "(разом)"].set_index("підклас")["енергія_мвт_год"]
q1_total = q1.loc[q1["клас"] == "УСЬОГО", "енергія_мвт_год"].iloc[0]
print("1) ROLLUP за таксономією, МВт·год")
for label in p1.index:
    same = abs(p1[label] - q1_sub[label]) < 0.01
    ok_all &= same
    print(f"   {label:22s} pandas={p1[label]:9.2f}  SQL={q1_sub[label]:9.2f}  {'OK' if same else 'РОЗБІЖНІСТЬ'}")
same = abs(p1_total - q1_total) < 0.01
ok_all &= same
print(f"   {'УСЬОГО':22s} pandas={p1_total:9.2f}  SQL={q1_total:9.2f}  {'OK' if same else 'РОЗБІЖНІСТЬ'}")

# 2) накопичення і ковзне середнє
daily = fact.merge(dates, on="date_key").groupby("date")["energy_kwh"].sum().sort_index()
p7 = pd.DataFrame({"cum": (daily.cumsum() / 1000).round(2),
                   "ma7": (daily.rolling(7, min_periods=1).mean() / 1000).round(2)})
q7 = sql("q07_window_cumulative.sql").set_index("дата")
q7.index = pd.to_datetime(q7.index)
p7.index = pd.to_datetime(p7.index)
d_cum = (p7["cum"] - q7["накопичено_мвт_год"]).abs().max()
d_ma = (p7["ma7"] - q7["ковз_7д_мвт_год"]).abs().max()
ok2 = d_cum < 0.011 and d_ma < 0.011
ok_all &= ok2
print("2) Віконні функції: 31 день")
print(f"   макс. різниця накопичення = {d_cum:.3f} МВт·год; ковзного середнього = {d_ma:.3f} МВт·год  "
      f"{'OK' if ok2 else 'РОЗБІЖНІСТЬ'}")
print(f"   31.01: pandas cum={p7['cum'].iloc[-1]}, ma7={p7['ma7'].iloc[-1]}; "
      f"SQL cum={q7['накопичено_мвт_год'].iloc[-1]}, ma7={q7['ковз_7д_мвт_год'].iloc[-1]}")
print("ПІДСУМОК:", "обидва результати підтверджено" if ok_all else "є розбіжності")
