-- Питання: B1. Скільки енергії спожито за січень 2026 за класами таксономії (клас → підклас) і разом?
-- Конструкція: ROLLUP + GROUPING()
-- Інтерпретація: за січень спожито 1926,23 МВт·год; 77,0 % припадає на промислових споживачів (7 споживачів), 18,9 % — на комерційних, 4,1 % — на побутових (23 споживачі). Рядки ROLLUP із GROUPING() = 1 — підсумки за класом :Consumer і загальний; вони збігаються, бо корінь таксономії один.
SELECT CASE WHEN GROUPING(k.parent_label) = 1 THEN 'УСЬОГО' ELSE k.parent_label END AS клас,
       CASE WHEN GROUPING(k.class_label) = 1 THEN '(разом)' ELSE k.class_label END AS підклас,
       replace(k.class_iri, 'http://www.semanticweb.org/energy-forecasting#', 'ef:') AS iri,
       round(sum(f.energy_kwh) / 1000, 2) AS енергія_мвт_год,
       round(100 * sum(f.energy_kwh) / (SELECT sum(energy_kwh) FROM fact_consumption), 1) AS частка_pct
FROM fact_consumption f JOIN dim_consumer_class k USING (class_key)
GROUP BY ROLLUP (k.parent_label, (k.class_label, k.class_iri))
ORDER BY GROUPING(k.parent_label), GROUPING(k.class_label), енергія_мвт_год DESC;
