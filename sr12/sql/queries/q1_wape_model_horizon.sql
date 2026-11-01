-- Питання: 1. Яка точність (WAPE) кожної моделі на кожному горизонті?
-- WAPE — неадитивна: рахується з адитивних складових sum(|e|) / sum(факт), а не як середнє ape_pct
SELECT m.model_name AS модель, h.horizon_label AS горизонт,
       count(*) AS прогнозів,
       round(100 * sum(f.abs_error_kwh) / sum(f.actual_kwh), 2) AS wape_pct
FROM fact_forecast f
JOIN dim_model m USING (model_key)
JOIN dim_horizon h USING (horizon_key)
GROUP BY m.model_name, h.horizon_label, h.horizon_days
ORDER BY h.horizon_days, wape_pct;
