-- Питання: 4. На яких підстанціях і в яких областях прогнози систематично завищені чи занижені (горизонт 1 доба)?
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
