-- Питання: B6. Як відрізняється середнє добове споживання в будні й вихідні за класами (з усіма підсумками)?
-- Конструкція: CUBE (клас × тип дня) + GROUPING()
-- Інтерпретація: у вихідні добове споживання всієї мережі падає з 72,05 до 37,91 МВт·год (−47 %) через промислових (−50 %) і комерційних (−48,5 %) споживачів; у побутових навпаки зростає з 2,48 до 2,68 МВт·год/добу (+8 %). CUBE дає всі 12 комбінацій підсумків одним запитом.
SELECT CASE WHEN GROUPING(k.class_label) = 1 THEN 'усі класи' ELSE k.class_label END AS клас,
       CASE WHEN GROUPING(d.is_weekend) = 1 THEN 'усі дні'
            WHEN d.is_weekend THEN 'вихідні' ELSE 'будні' END AS тип_дня,
       count(DISTINCT d.date_key) AS днів,
       round(sum(f.energy_kwh) / 1000, 2) AS енергія_мвт_год,
       round(sum(f.energy_kwh) / 1000 / count(DISTINCT d.date_key), 2) AS мвт_год_на_добу
FROM fact_consumption f
JOIN dim_consumer_class k USING (class_key)
JOIN dim_date d USING (date_key)
GROUP BY CUBE (k.class_label, d.is_weekend)
ORDER BY GROUPING(k.class_label), k.class_label, GROUPING(d.is_weekend), d.is_weekend;
