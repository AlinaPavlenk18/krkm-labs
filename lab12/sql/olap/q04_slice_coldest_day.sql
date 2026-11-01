-- Питання: B3. Зріз за одним днем: як розподілялося споживання за частинами доби в найхолодніший день 11.01.2026 (−15,5 °C у Львові за графом ЛР9)?
-- Конструкція: SLICE (dim_date = 2026-01-11) + розподіл за частиною доби й класом
-- Інтерпретація: у найхолодніший день (неділя) комерційні споживачі мають денний максимум (3251 кВт·год), побутові — вечірній (1155,5 кВт·год), промислові споживають рівно протягом доби (вихідний: одна зміна не працює). Найнижча температура — вночі (−18,3 °C).
SELECT h.part_of_day AS частина_доби,
       round(sum(f.energy_kwh) FILTER (WHERE k.class_label = 'Побутовий споживач'), 1)   AS побутові_квт_год,
       round(sum(f.energy_kwh) FILTER (WHERE k.class_label = 'Комерційний споживач'), 1) AS комерційні_квт_год,
       round(sum(f.energy_kwh) FILTER (WHERE k.class_label = 'Промисловий споживач'), 1) AS промислові_квт_год,
       round(avg(f.temperature_c), 1) AS сер_темп_c
FROM fact_consumption f
JOIN dim_date d USING (date_key)
JOIN dim_hour h USING (hour_key)
JOIN dim_consumer_class k USING (class_key)
WHERE d.date = DATE '2026-01-11'
GROUP BY h.part_of_day
ORDER BY min(h.hour_key);
