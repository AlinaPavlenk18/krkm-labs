"""Семантичний шар: генерація SQL за назвою метрики з semantic/metrics.yml."""
from pathlib import Path
import yaml

SPEC = yaml.safe_load((Path(__file__).with_name("metrics.yml")).read_text(encoding="utf-8"))
METRICS = {m["name"]: m for m in SPEC["metrics"]}
DIMS = SPEC["dimensions"]
JOINS = """FROM fact_consumption f
    JOIN dim_consumer_class k USING (class_key)
    JOIN dim_consumer c USING (consumer_key)
    JOIN dim_substation s USING (substation_key)
    JOIN dim_date d USING (date_key)
    JOIN dim_hour h USING (hour_key)"""


def _literal(v):
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _where(where: dict) -> str:
    conds = []
    for dim, val in (where or {}).items():
        if dim not in DIMS:
            raise ValueError(f"невідомий вимір: {dim}")
        if isinstance(val, (list, tuple)):
            conds.append(f"{DIMS[dim]} IN ({', '.join(_literal(v) for v in val)})")
        else:
            conds.append(f"{DIMS[dim]} = {_literal(val)}")
    return ("\n    WHERE " + " AND ".join(conds)) if conds else ""


def metric_sql(name: str, by: list[str] | None = None, where: dict | None = None) -> str:
    if name not in METRICS:
        raise ValueError(f"невідома метрика: {name}; доступні: {', '.join(METRICS)}")
    m, by = METRICS[name], by or []
    for dim in by:
        if dim not in DIMS:
            raise ValueError(f"невідомий вимір: {dim}")
    sel = "".join(f"{DIMS[d]} AS {d}, " for d in by)
    group = f"\nGROUP BY {', '.join(by)}\nORDER BY {', '.join(by)}" if by else ""
    if m["type"] == "simple":
        return f"SELECT {sel}{m['sql']} AS {name}\n    {JOINS}{_where(where)}{group};"
    inner_keys = "f.date_key, f.hour_key" + (", f.consumer_key" if m["type"] == "hourly_consumer" else "")
    limit_col = ", any_value(c.contract_limit_kw) AS contract_limit_kw" if m["type"] == "hourly_consumer" else ""
    outer_sel = "".join(f"{d}, " for d in by)
    return (f"WITH hourly AS (\n    SELECT {sel}{inner_keys}, sum(f.energy_kwh) AS load_kw{limit_col}\n    {JOINS}"
            f"{_where(where)}\n    GROUP BY ALL)\nSELECT {outer_sel}{m['sql']} AS {name}\nFROM hourly{group};")


if __name__ == "__main__":
    import sys
    print(metric_sql(sys.argv[1] if len(sys.argv) > 1 else "total_energy", by=sys.argv[2:]))
