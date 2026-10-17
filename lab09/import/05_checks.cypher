// ЛР9 · Результат 2 · Крок 4. Перевірки після імпорту (виконуйте по одному запиту; результати — у звіт).

// 5.1 Кількість вузлів і зв'язків (очікувано: 190 і 314)
MATCH (n) WITH count(n) AS nodes
MATCH ()-[r]->() RETURN nodes, count(r) AS relationships;

// 5.2 Розподіл за мітками
MATCH (n) UNWIND labels(n) AS label
RETURN label, count(*) AS cnt ORDER BY cnt DESC;

// 5.3 Розподіл за типами зв'язків
MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS cnt ORDER BY cnt DESC;

// 5.4 Обмеження та індекси
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties;
SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, owningConstraint;

// 5.5 Контроль цілісності «як у SHACL ЛР8»: споживач без лічильника, прогноз не від однієї моделі
MATCH (c:Consumer) WHERE NOT (c)-[:HAS_METER]->(:Meter) RETURN 'consumer without meter' AS check, count(c) AS violations
UNION ALL
MATCH (f:Forecast) WHERE COUNT { (:ForecastModel)-[:GENERATED]->(f) } <> 1 RETURN 'forecast not from exactly 1 model' AS check, count(f) AS violations
UNION ALL
MATCH (s:Substation) WHERE COUNT { (:Dispatcher)-[:MANAGES]->(s) } > 1 RETURN 'substation with >1 dispatcher' AS check, count(s) AS violations;
