# Семантичний шар (ЛР12, результат 4)

Специфікація: `semantic/metrics.yml` (версія 1.0.0), генератор SQL: `semantic/semantic.py` → `metric_sql(name, by, where)`.

## Метрики

| Метрика | Назва | Одиниця | Тип | Власник | Перегляд | Статус |
|---|---|---|---|---|---|---|
| `total_energy` | Спожита енергія | кВт·год | simple | Павленко А. С. (аналітик даних Domain Knowledge Hub) | 2026-10-31 | approved |
| `peak_load` | Пікове годинне навантаження | кВт | hourly | Павленко А. С. (аналітик даних Domain Knowledge Hub) | 2026-10-31 | approved |
| `avg_load` | Середнє годинне навантаження | кВт | hourly | Павленко А. С. (аналітик даних Domain Knowledge Hub) | 2026-10-31 | approved |
| `load_factor` | Коефіцієнт навантаження | частка (0–1) | hourly | Павленко А. С. (аналітик даних Domain Knowledge Hub) | 2026-10-31 | approved |
| `over_limit_hours` | Години перевищення договірного ліміту | год | hourly_consumer | Павленко А. С. (аналітик даних Domain Knowledge Hub) | 2026-10-31 | approved |
| `peak_share` | Частка енергії в пікові години | % | simple | Павленко А. С. (аналітик даних Domain Knowledge Hub) | 2026-10-31 | approved |
| `energy_per_meter_day` | Добова енергія на активний лічильник | кВт·год/добу | simple | Павленко А. С. (аналітик даних Domain Knowledge Hub) | 2026-10-31 | draft |

## Приклад згенерованого SQL

```python
metric_sql('over_limit_hours', by=['consumer'], where={'consumer': 'Consumer_3310'})
```

```sql
WITH hourly AS (
    SELECT c.consumer_id AS consumer, f.date_key, f.hour_key, f.consumer_key, sum(f.energy_kwh) AS load_kw, any_value(c.contract_limit_kw) AS contract_limit_kw
    FROM fact_consumption f
    JOIN dim_consumer_class k USING (class_key)
    JOIN dim_consumer c USING (consumer_key)
    JOIN dim_substation s USING (substation_key)
    JOIN dim_date d USING (date_key)
    JOIN dim_hour h USING (hour_key)
    WHERE c.consumer_id = 'Consumer_3310'
    GROUP BY ALL)
SELECT consumer, count(*) FILTER (WHERE load_kw > contract_limit_kw) AS over_limit_hours
FROM hourly
GROUP BY consumer
ORDER BY consumer;
```

## Узгодженість результатів різними шляхами

| Питання | Шлях A | A | Шлях B | B | Висновок |
|---|---|---|---|---|---|
| П1. Енергія, МВт·год — Комерційний споживач | semantic total_energy | 363.6 | OLAP q01 (ROLLUP) | 363.6 | збігається |
| П1. Енергія, МВт·год — Комерційний споживач | semantic total_energy | 363.6 | pandas (Parquet) | 363.6 | збігається |
| П1. Енергія, МВт·год — Побутовий споживач | semantic total_energy | 78.69 | OLAP q01 (ROLLUP) | 78.69 | збігається |
| П1. Енергія, МВт·год — Побутовий споживач | semantic total_energy | 78.69 | pandas (Parquet) | 78.69 | збігається |
| П1. Енергія, МВт·год — Промисловий споживач | semantic total_energy | 1483.93 | OLAP q01 (ROLLUP) | 1483.93 | збігається |
| П1. Енергія, МВт·год — Промисловий споживач | semantic total_energy | 1483.93 | pandas (Parquet) | 1483.93 | збігається |
| П2. Пікове навантаження, кВт — Підстанція №12 | semantic peak_load | 300.48 | OLAP q08 (вікна) | 300.5 | збігається |
| П2. Пікове навантаження, кВт — Підстанція №1 | semantic peak_load | 1076.58 | OLAP q08 (вікна) | 1076.6 | збігається |
| П2. Пікове навантаження, кВт — Підстанція №5 | semantic peak_load | 455.5 | OLAP q08 (вікна) | 455.5 | збігається |
| П3. Години перевищення ліміту — Consumer_3310 | semantic over_limit_hours | 86 | OLAP q09 (SCD 2) | 86 | збігається |

Усі порівняння: збігаються.

## Наївні запити без семантичного шару

| Запит | Наївний результат | Метрика семантичного шару |
|---|---|---|
| Пік ПС №12 як max(energy_kwh) одного показання | 275.69 | 300.48 |
| Перевищення Consumer_3310 за поточним лімітом (без SCD 2) | 1 | 86 |
