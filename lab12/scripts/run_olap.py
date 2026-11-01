"""Виконує sql/olap/*.sql і збирає docs/olap_results.md (питання, конструкція, запит, результат, інтерпретація)."""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]


def header(sql: str, key: str) -> str:
    for line in sql.splitlines():
        if line.startswith(f"-- {key}:"):
            return line.split(":", 1)[1].strip()
    return ""


def main():
    con = duckdb.connect(str(ROOT / "data/warehouse.duckdb"), read_only=True)
    out = ["# Результати OLAP-запитів (ЛР12, результат 3)", ""]
    for f in sorted((ROOT / "sql/olap").glob("q*.sql")):
        sql = f.read_text(encoding="utf-8")
        df = con.sql(sql).df()
        body = "\n".join(l for l in sql.splitlines() if not l.startswith("--"))
        out += [f"## {f.stem}", "",
                f"**Питання.** {header(sql, 'Питання')}", "",
                f"**Конструкція.** {header(sql, 'Конструкція')}", "",
                "```sql", body.strip(), "```", "",
                f"**Результат** ({len(df)} рядків):", "",
                df.to_markdown(index=False), "",
                f"**Інтерпретація.** {header(sql, 'Інтерпретація')}", ""]
        print(f"{f.name}: {len(df)} рядків")
    (ROOT / "docs/olap_results.md").write_text("\n".join(out), encoding="utf-8")
    print("→ docs/olap_results.md")


if __name__ == "__main__":
    main()
