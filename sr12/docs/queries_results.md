# Перевірка схеми й 5 запитів (СР12)

| Перевірка | Значення |
|---|---|
| рядків факту | 2232 |
| «сироти» (усі 6 FK) | 0 |
| дата складання ≠ цільова − горизонт | 0 |
| прогноз складено версією, не чинною на дату складання | 0 |

## q1_wape_model_horizon

**Питання.** 1. Яка точність (WAPE) кожної моделі на кожному горизонті?

```sql
SELECT m.model_name AS модель, h.horizon_label AS горизонт,
       count(*) AS прогнозів,
       round(100 * sum(f.abs_error_kwh) / sum(f.actual_kwh), 2) AS wape_pct
FROM fact_forecast f
JOIN dim_model m USING (model_key)
JOIN dim_horizon h USING (horizon_key)
GROUP BY m.model_name, h.horizon_label, h.horizon_days
ORDER BY h.horizon_days, wape_pct;
```

| модель                     | горизонт       |   прогнозів |   wape_pct |
|:---------------------------|:---------------|------------:|-----------:|
| Модель LSTM №1             | 1 доба наперед |         372 |       4.65 |
| Модель VAR №1              | 1 доба наперед |         372 |       5.6  |
| Модель LSTM №2 (застаріла) | 1 доба наперед |         372 |       7.81 |
| Модель LSTM №1             | 7 діб наперед  |         372 |       7.76 |
| Модель VAR №1              | 7 діб наперед  |         372 |       8.13 |
| Модель LSTM №2 (застаріла) | 7 діб наперед  |         372 |      12.26 |

## q2_rollup_taxonomy

**Питання.** 2. Як відрізняється точність статистичних моделей і моделей машинного навчання (з підсумком)?

```sql
SELECT coalesce(k.class_label, 'УСІ МОДЕЛІ') AS клас_моделі,
       coalesce(m.model_name, '(разом за класом)') AS модель,
       round(100 * sum(f.abs_error_kwh) / sum(f.actual_kwh), 2) AS wape_pct,
       round(100 * sum(f.error_kwh) / sum(f.actual_kwh), 2) AS зсув_pct
FROM fact_forecast f
JOIN dim_model_class k USING (class_key)
JOIN dim_model m USING (model_key)
WHERE f.horizon_key = 1
GROUP BY ROLLUP (k.class_label, m.model_name)
ORDER BY GROUPING(k.class_label), k.class_label, GROUPING(m.model_name), m.model_name;
```

| клас_моделі               | модель                     |   wape_pct |   зсув_pct |
|:--------------------------|:---------------------------|-----------:|-----------:|
| Модель машинного навчання | Модель LSTM №1             |       4.65 |       0.2  |
| Модель машинного навчання | Модель LSTM №2 (застаріла) |       7.81 |      -3.64 |
| Модель машинного навчання | (разом за класом)          |       6.23 |      -1.72 |
| Статистична модель        | Модель VAR №1              |       5.6  |       3.19 |
| Статистична модель        | (разом за класом)          |       5.6  |       3.19 |
| УСІ МОДЕЛІ                | (разом за класом)          |       6.02 |      -0.08 |

## q3_scd2_retraining

**Питання.** 3. Чи покращилася модель LSTM №1 після перенавчання 15.01.2026 (версії SCD 2)?

```sql
SELECT m.version AS версія, m.training_date AS навчена, m.valid_from AS діє_з, m.valid_to AS діє_до,
       h.horizon_label AS горизонт, count(*) AS прогнозів,
       round(100 * sum(f.abs_error_kwh) / sum(f.actual_kwh), 2) AS wape_pct
FROM fact_forecast f
JOIN dim_model m USING (model_key)
JOIN dim_horizon h USING (horizon_key)
WHERE m.model_id = 'ForecastModel_LSTM1'
GROUP BY ALL
ORDER BY h.horizon_label, m.version;
```

|   версія | навчена             | діє_з               | діє_до              | горизонт       |   прогнозів |   wape_pct |
|---------:|:--------------------|:--------------------|:--------------------|:---------------|------------:|-----------:|
|        1 | 2025-10-01 00:00:00 | 2025-10-01 00:00:00 | 2026-01-14 00:00:00 | 1 доба наперед |         180 |       5.95 |
|        2 | 2026-01-15 00:00:00 | 2026-01-15 00:00:00 | 9999-12-31 00:00:00 | 1 доба наперед |         192 |       3.4  |
|        1 | 2025-10-01 00:00:00 | 2025-10-01 00:00:00 | 2026-01-14 00:00:00 | 7 діб наперед  |         252 |       8.78 |
|        2 | 2026-01-15 00:00:00 | 2026-01-15 00:00:00 | 9999-12-31 00:00:00 | 7 діб наперед  |         120 |       5.56 |

## q4_bias_region

**Питання.** 4. На яких підстанціях і в яких областях прогнози систематично завищені чи занижені (горизонт 1 доба)?

```sql
SELECT coalesce(s.region_name, 'УСІ ОБЛАСТІ') AS область,
       coalesce(s.substation_name, '(разом)') AS підстанція,
       round(100 * sum(f.error_kwh) / sum(f.actual_kwh), 2) AS зсув_pct,
       round(100 * sum(f.abs_error_kwh) / sum(f.actual_kwh), 2) AS wape_pct
FROM fact_forecast f
JOIN dim_substation s USING (substation_key)
WHERE f.horizon_key = 1
GROUP BY ROLLUP (s.region_name, s.substation_name)
HAVING GROUPING(s.substation_name) = 1 OR abs(100 * sum(f.error_kwh) / sum(f.actual_kwh)) >= 1.5
ORDER BY GROUPING(s.region_name), s.region_name, GROUPING(s.substation_name), зсув_pct DESC;
```

| область                   | підстанція     |   зсув_pct |   wape_pct |
|:--------------------------|:---------------|-----------:|-----------:|
| Івано-Франківська область | (разом)        |      -0.75 |       6.11 |
| Волинська область         | (разом)        |       0.23 |       6.33 |
| Закарпатська область      | (разом)        |       0.35 |       5.62 |
| Львівська область         | Підстанція №10 |       1.63 |       6.76 |
| Львівська область         | (разом)        |      -0.11 |       5.95 |
| Рівненська область        | (разом)        |      -1.16 |       6.33 |
| Тернопільська область     | (разом)        |      -0.68 |       5.78 |
| УСІ ОБЛАСТІ               | (разом)        |      -0.08 |       6.02 |

## q5_semiadditive_mtd

**Питання.** 5. Яку накопичену з початку місяця абсолютну похибку мала кожна модель на кінець місяця?

```sql
WITH by_model AS (
    SELECT m.model_id, h.horizon_label, t.date, f.mtd_abs_error_kwh, f.abs_error_kwh
    FROM fact_forecast f
    JOIN dim_model m USING (model_key)
    JOIN dim_horizon h USING (horizon_key)
    JOIN dim_date t ON t.date_key = f.target_date_key)
SELECT model_id AS модель, horizon_label AS горизонт,
       round(sum(mtd_abs_error_kwh) FILTER (WHERE date = DATE '2026-01-31') / 1000, 2) AS на_31_01_мвт_год,
       round(sum(abs_error_kwh) / 1000, 2)     AS перевірка_сума_похибок,
       round(sum(mtd_abs_error_kwh) / 1000, 2) AS хибно_сума_за_всі_дати
FROM by_model
GROUP BY ALL
ORDER BY горизонт, на_31_01_мвт_год;
```

| модель              | горизонт       |   на_31_01_мвт_год |   перевірка_сума_похибок |   хибно_сума_за_всі_дати |
|:--------------------|:---------------|-------------------:|-------------------------:|-------------------------:|
| ForecastModel_LSTM1 | 1 доба наперед |              89.63 |                    89.63 |                  1592.23 |
| ForecastModel_VAR1  | 1 доба наперед |             107.89 |                   107.89 |                  1750.49 |
| ForecastModel_LSTM2 | 1 доба наперед |             150.53 |                   150.53 |                  2409.18 |
| ForecastModel_LSTM1 | 7 діб наперед  |             149.5  |                   149.5  |                  2659.33 |
| ForecastModel_VAR1  | 7 діб наперед  |             156.59 |                   156.59 |                  2543.87 |
| ForecastModel_LSTM2 | 7 діб наперед  |             236.09 |                   236.09 |                  3686.49 |
