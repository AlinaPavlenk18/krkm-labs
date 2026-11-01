"""ЛР12 · Перевірка захистів text-to-SQL без LLM: AST-фільтр, LIMIT, read-only, тайм-аут."""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from t2sql.t2sql import guard, execute, connect, Rejected, MAX_ROWS 

ATTACKS = [
    "DROP TABLE dim_consumer",
    "DELETE FROM fact_consumption WHERE meter_id = 'Meter_AMI10452'",
    "SELECT 1; DROP TABLE dim_consumer",
    "UPDATE dim_consumer SET contract_limit_kw = 0",
    "CREATE TABLE x AS SELECT * FROM dim_consumer",
    "COPY dim_consumer TO 'C:/temp/consumers.csv'",
    "SELECT * FROM read_csv('C:/Windows/win.ini')",
    "SELECT * FROM 'data/raw/readings.csv'",
    "ATTACH 'other.duckdb' AS o",
    "SET enable_external_access = true",
    "PRAGMA database_list",
    "SELECT * FROM duckdb_settings()",
    "INSTALL httpfs",
]
SAFE = [
    "SELECT count(*) FROM fact_consumption",
    "WITH t AS (SELECT * FROM dim_hour) SELECT * FROM t",
    "SELECT * FROM fact_consumption",                       # без LIMIT → має отримати LIMIT 200
    "SELECT * FROM dim_date LIMIT 1000",                    # LIMIT > 200 → зменшити
]

ok = True
print("1) Атаки (мають бути відхилені на рівні AST):")
for s in ATTACKS:
    try:
        guard(s)
        print(f"   ПРОПУЩЕНО ✗  {s}")
        ok = False
    except Rejected as e:
        print(f"   відхилено ✓  {s}  —  {e}")

print("2) Безпечні запити (пропущені, LIMIT ≤ 200):")
for s in SAFE:
    g = guard(s)
    n = len(execute(g))
    good = n <= MAX_ROWS
    ok &= good
    print(f"   {'✓' if good else '✗'} {n:4d} рядків  {g}")

print("3) Read-only з'єднання (другий рубіж, якщо AST-фільтр обійдено):")
con = connect()
for s in ["CREATE TABLE x (a INT)", "COPY dim_hour TO 'x.csv'", "SET enable_external_access = true"]:
    try:
        con.execute(s)
        print(f"   ВИКОНАНО ✗  {s}")
        ok = False
    except Exception as e:  
        print(f"   заблоковано ✓  {s}  —  {type(e).__name__}")
con.close()

print("4) Тайм-аут (важкий запит, ліміт 3 с):")
heavy = ("SELECT count(*) FROM fact_consumption a, fact_consumption b, dim_hour h "
         "WHERE a.energy_kwh + b.energy_kwh > h.hour_key")
t0 = time.time()
try:
    execute(guard(heavy), timeout_s=3)
    print("   не перервано ✗")
    ok = False
except Exception as e: 
    print(f"   перервано ✓ через {time.time() - t0:.1f} с — {type(e).__name__}")

print("ПІДСУМОК:", "усі захисти працюють" if ok else "є проблеми")
