-- Питання: 5. Яку накопичену з початку місяця абсолютну похибку мала кожна модель на кінець місяця?
-- mtd_abs_error_kwh — напівадитивна: сумується за підстанціями на одну дату (31.01), але не за датами
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
