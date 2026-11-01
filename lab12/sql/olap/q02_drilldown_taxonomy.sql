-- Питання: B1 (деталізація). Drill-down по таксономії: підклас ef:CommercialConsumer → окремі споживачі; хто дає найбільший внесок?
-- Конструкція: GROUPING SETS (підклас; підклас + споживач) — drill-down на рівень нижче
-- Інтерпретація: drill-down на рівень нижче підкласу ef:CommercialConsumer: 11 споживачів, жоден не перевищує 13,4 % підкласу — споживання розподілене рівномірно; Consumer_3310 (8,4 %) — 8-й, попри перевищення ліміту, бо ліміт у нього нижчий, ніж у найбільших.
SELECT replace(k.class_iri, 'http://www.semanticweb.org/energy-forecasting#', 'ef:') AS iri,
       coalesce(c.consumer_id, '(разом за підкласом)') AS споживач,
       round(sum(f.energy_kwh) / 1000, 2) AS енергія_мвт_год,
       round(100 * sum(f.energy_kwh) / sum(sum(f.energy_kwh)) OVER (PARTITION BY GROUPING(c.consumer_id)), 1) AS частка_pct
FROM fact_consumption f
JOIN dim_consumer_class k USING (class_key)
JOIN dim_consumer c USING (consumer_key)
WHERE k.class_iri = 'http://www.semanticweb.org/energy-forecasting#CommercialConsumer'
GROUP BY GROUPING SETS ((k.class_iri), (k.class_iri, c.consumer_id))
ORDER BY GROUPING(c.consumer_id) DESC, енергія_мвт_год DESC;
