-- Питання: 2. Як відрізняється точність статистичних моделей і моделей машинного навчання (з підсумком)?
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
