"""Виконує DDL зі схеми LLM (llm_log/qwen_schema_raw.md) у порожній DuckDB і показує, які оператори пройшли."""
import re
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / "llm_log/qwen_schema_raw.md").read_text(encoding="utf-8")
sql = re.search(r"```sql\n(.*?)```", raw, re.S).group(1)
con = duckdb.connect()
for st in [s.strip() for s in sql.split(";") if s.strip()]:
    body = "\n".join(l for l in st.splitlines() if not l.strip().startswith("--")).strip()
    head = " ".join(body.split()[:6])
    try:
        con.execute(body)
        print(f"OK    {head}")
    except Exception as e:  
        print(f"FAIL  {head}  —  {type(e).__name__}: {str(e)[:90]}")
fks = con.execute("SELECT count(*) FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'").fetchall()[0][0]
print(f"Зовнішніх ключів у створеній схемі: {fks}")
