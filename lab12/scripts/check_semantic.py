import sys
from pathlib import Path
import duckdb, pandas as pd, yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic.semantic import metric_sql, METRICS  

con = duckdb.connect(str(ROOT / "data/warehouse.duckdb"), read_only=True)
q = lambda s: con.sql(s).df()
olap = lambda n: q((ROOT / "sql/olap" / n).read_text(encoding="utf-8"))
rows, ok_all = [], True


def compare(question, path_a, a, path_b, b, tol=0.01):
    global ok_all
    same = abs(a - b) <= tol
    ok_all &= same
    rows.append((question, path_a, round(a, 2), path_b, round(b, 2), "збігається" if same else "РІЗНИТЬСЯ"))


# П1. Енергія за підкласами таксономії: семантичний шар vs OLAP q01 vs pandas
sem = q(metric_sql("total_energy", by=["class"])).set_index("class")["total_energy"] / 1000
o1 = olap("q01_rollup_taxonomy.sql")
o1 = o1[o1["підклас"] != "(разом)"].set_index("підклас")["енергія_мвт_год"]
fact = pd.read_parquet(ROOT / "data/fact_consumption.parquet")
cls = pd.read_parquet(ROOT / "data/dim_consumer_class.parquet")
pdv = fact.merge(cls, on="class_key").groupby("class_label")["energy_kwh"].sum() / 1000
for c in sem.index:
    compare(f"П1. Енергія, МВт·год — {c}", "semantic total_energy", sem[c], "OLAP q01 (ROLLUP)", o1[c])
    compare(f"П1. Енергія, МВт·год — {c}", "semantic total_energy", sem[c], "pandas (Parquet)", pdv[c])

# П2. Пікове навантаження підстанцій: семантичний шар vs OLAP q08
sem2 = q(metric_sql("peak_load", by=["substation"])).set_index("substation")["peak_load"]
o8 = olap("q08_window_rank_substation.sql").set_index("підстанція")["пік_квт"]
for st in ["Підстанція №12", "Підстанція №1", "Підстанція №5"]:
    compare(f"П2. Пікове навантаження, кВт — {st}", "semantic peak_load", sem2[st], "OLAP q08 (вікна)", o8[st], tol=0.06)

# П3. Години перевищення ліміту Consumer_3310: семантичний шар vs OLAP q09 (сума версій SCD 2)
sem3 = q(metric_sql("over_limit_hours", by=["consumer"], where={"consumer": "Consumer_3310"}))["over_limit_hours"].iloc[0]
o9 = olap("q09_scd2_over_limit.sql")
o9v = o9.loc[o9["споживач"] == "Consumer_3310", "годин_перевищення"].sum()
compare("П3. Години перевищення ліміту — Consumer_3310", "semantic over_limit_hours", sem3, "OLAP q09 (SCD 2)", o9v)

# «Наївні» шляхи без семантичного шару — інші відповіді на ті самі питання
naive_peak = q("SELECT max(f.energy_kwh) AS v FROM fact_consumption f JOIN dim_substation s USING (substation_key) "
               "WHERE s.substation_name = 'Підстанція №12'")["v"].iloc[0]
naive_over = q("""WITH h AS (SELECT consumer_key, date_key, hour_key, sum(energy_kwh) AS load_kw
                  FROM fact_consumption GROUP BY ALL)
                  SELECT count(*) AS v FROM h JOIN dim_consumer c0 USING (consumer_key)
                  JOIN dim_consumer c ON c.consumer_id = c0.consumer_id AND c.is_current
                  WHERE c0.consumer_id = 'Consumer_3310' AND h.load_kw > c.contract_limit_kw""")["v"].iloc[0]
naive = [("Пік ПС №12 як max(energy_kwh) одного показання", round(naive_peak, 2), round(sem2["Підстанція №12"], 2)),
         ("Перевищення Consumer_3310 за поточним лімітом (без SCD 2)", int(naive_over), int(sem3))]

md = ["# Семантичний шар (ЛР12, результат 4)", "",
      f"Специфікація: `semantic/metrics.yml` (версія {yaml.safe_load((ROOT / 'semantic/metrics.yml').read_text(encoding='utf-8'))['version']}), "
      "генератор SQL: `semantic/semantic.py` → `metric_sql(name, by, where)`.", "",
      "## Метрики", "", "| Метрика | Назва | Одиниця | Тип | Власник | Перегляд | Статус |", "|---|---|---|---|---|---|---|"]
for m in METRICS.values():
    md.append(f"| `{m['name']}` | {m['label']} | {m['unit']} | {m['type']} | {m['owner']} | {m['review_date']} | {m['status']} |")
md += ["", "## Приклад згенерованого SQL", "", "```python",
       "metric_sql('over_limit_hours', by=['consumer'], where={'consumer': 'Consumer_3310'})", "```", "", "```sql",
       metric_sql("over_limit_hours", by=["consumer"], where={"consumer": "Consumer_3310"}), "```", "",
       "## Узгодженість результатів різними шляхами", "",
       "| Питання | Шлях A | A | Шлях B | B | Висновок |", "|---|---|---|---|---|---|"]
md += [f"| {' | '.join(map(str, r))} |" for r in rows]
md += ["", f"Усі порівняння: {'збігаються' if ok_all else 'є розбіжності'}.", "",
       "## Наївні запити без семантичного шару", "", "| Запит | Наївний результат | Метрика семантичного шару |", "|---|---|---|"]
md += [f"| {a} | {b} | {c} |" for a, b, c in naive]
(ROOT / "docs/semantic_layer.md").write_text("\n".join(md) + "\n", encoding="utf-8")

for r in rows:
    print(" | ".join(map(str, r)))
for a, b, c in naive:
    print(f"НАЇВНО: {a}: {b}  ↔  семантичний шар: {c}")
print("ПІДСУМОК:", "усі шляхи узгоджені" if ok_all else "є розбіжності")
