-- Питання: B2. Підкуб: скільки енергії побутові й комерційні споживачі Львівської та Волинської областей спожили в пікові години будніх днів?
-- Конструкція: DICE (область ∈ {Львівська, Волинська} × клас ∈ {побутовий, комерційний} × is_peak × будні)
-- Інтерпретація: у підкубі (2 області × 2 класи × пікові години × будні) комерційні лічильники Волинської області споживають у пік більше на лічильник (11 459,7 кВт·год), ніж львівські (8928,8), а побутові — навпаки (961,8 проти 1084,9). Основне пікове навантаження в обох областях створюють комерційні споживачі.
SELECT s.region_name AS область, k.class_label AS клас,
       count(DISTINCT f.meter_id) AS лічильників,
       round(sum(f.energy_kwh), 1) AS пік_квт_год,
       round(sum(f.energy_kwh) / count(DISTINCT f.meter_id), 1) AS на_лічильник_квт_год
FROM fact_consumption f
JOIN dim_substation s USING (substation_key)
JOIN dim_consumer_class k USING (class_key)
JOIN dim_hour h USING (hour_key)
JOIN dim_date d USING (date_key)
WHERE s.region_name IN ('Львівська область', 'Волинська область')
  AND k.class_label IN ('Побутовий споживач', 'Комерційний споживач')
  AND h.is_peak AND NOT d.is_weekend
GROUP BY ALL
ORDER BY область, клас;
