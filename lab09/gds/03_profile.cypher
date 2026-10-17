// ЛР9 · Крок 3. PROFILE двох запитів і оптимізація «до / після».

// ===== Запит A: вимірювання за період (оптимізація ІНДЕКСОМ) =====
// A-ДО: індексу на Measurement.timestamp ще немає → NodeByLabelScan + Filter
DROP INDEX measurement_ts IF EXISTS;
PROFILE
MATCH (x:Measurement)
WHERE x.timestamp >= localdatetime('2026-09-28T00:00:00') AND x.timestamp < localdatetime('2026-09-30T00:00:00')
RETURN x.id, x.timestamp, x.consumptionValue ORDER BY x.timestamp;

// створюємо індекс і чекаємо, доки він стане ONLINE
CREATE INDEX measurement_ts IF NOT EXISTS FOR (x:Measurement) ON (x.timestamp);
CALL db.awaitIndexes(60);

// A-ПІСЛЯ: той самий запит → NodeIndexSeekByRange (читаються лише потрібні вузли)
PROFILE
MATCH (x:Measurement)
WHERE x.timestamp >= localdatetime('2026-09-28T00:00:00') AND x.timestamp < localdatetime('2026-09-30T00:00:00')
RETURN x.id, x.timestamp, x.consumptionValue ORDER BY x.timestamp;

// ===== Запит B: диспетчери, підстанції, прогнози (оптимізація ПЕРЕПИСУВАННЯМ) =====
// B-ДО: два OPTIONAL MATCH поспіль → проміжний декартів добуток (підстанції × прогнози) на кожного диспетчера
PROFILE
MATCH (d:Dispatcher)
OPTIONAL MATCH (d)-[:MANAGES]->(s:Substation)
OPTIONAL MATCH (d)-[:USES_FORECAST]->(f:Forecast)-[:FORECAST_FOR]->(fs:Substation)
RETURN d.id AS dispatcher, collect(DISTINCT s.id) AS managed,
       count(DISTINCT f) AS forecastsUsed, collect(DISTINCT fs.id) AS forecastTargets
ORDER BY dispatcher;

// B-ПІСЛЯ: агрегація підстанцій до WITH (= queries/q07) → кількість рядків не множиться, DISTINCT для s не потрібен
PROFILE
MATCH (d:Dispatcher)
OPTIONAL MATCH (d)-[:MANAGES]->(s:Substation)
WITH d, collect(s.id) AS managed
OPTIONAL MATCH (d)-[:USES_FORECAST]->(f:Forecast)-[:FORECAST_FOR]->(fs:Substation)
RETURN d.id AS dispatcher, managed, count(f) AS forecastsUsed, collect(DISTINCT fs.id) AS forecastTargets
ORDER BY dispatcher;
