-- Питання: B3. Наскільки добове споживання одного лічильника кожного класу залежить від температури (кореляція і нахил регресії)?
-- Конструкція: статистичні агрегати CORR() і REGR_SLOPE() над добовим зрізом
-- Інтерпретація: у будні споживання лічильника сильно залежить від температури: кореляція −0,958 для побутових, −0,771 для комерційних, −0,702 для промислових; кожен градус похолодання додає ≈ 2,1 / 14,2 / 21,8 кВт·год на добу на лічильник. Без розділення будні/вихідні кореляція для комерційних і промислових хибно додатна (0,184 і 0,250) — змішуються два режими роботи.
WITH daily AS (
    SELECT k.class_label AS клас, d.date, d.is_weekend,
           sum(f.energy_kwh) / count(DISTINCT f.meter_id) AS e, avg(f.temperature_c) AS t
    FROM fact_consumption f
    JOIN dim_consumer_class k USING (class_key)
    JOIN dim_date d USING (date_key)
    GROUP BY ALL)
SELECT клас,
       round(corr(e, t), 3) AS кореляція_всі_дні,
       round(corr(e, t) FILTER (WHERE NOT is_weekend), 3) AS кореляція_будні,
       round(regr_slope(e, t) FILTER (WHERE NOT is_weekend), 1) AS квт_год_на_1c_на_лічильник
FROM daily
GROUP BY клас
ORDER BY клас;
