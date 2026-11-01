-- Питання: 3. Чи покращилася модель LSTM №1 після перенавчання 15.01.2026 (версії SCD 2)?
SELECT m.version AS версія, m.training_date AS навчена, m.valid_from AS діє_з, m.valid_to AS діє_до,
       h.horizon_label AS горизонт, count(*) AS прогнозів,
       round(100 * sum(f.abs_error_kwh) / sum(f.actual_kwh), 2) AS wape_pct
FROM fact_forecast f
JOIN dim_model m USING (model_key)
JOIN dim_horizon h USING (horizon_key)
WHERE m.model_id = 'ForecastModel_LSTM1'
GROUP BY ALL
ORDER BY h.horizon_label, m.version;
