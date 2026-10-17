// Q7 · KQ8: Який диспетчер використовує які прогнози і якими підстанціями він керує?
// Конструкції: два OPTIONAL MATCH, розділені WITH (уникнення декартового добутку), collect DISTINCT
MATCH (d:Dispatcher)
OPTIONAL MATCH (d)-[:MANAGES]->(s:Substation)
WITH d, collect(s.id) AS managed
OPTIONAL MATCH (d)-[:USES_FORECAST]->(f:Forecast)-[:FORECAST_FOR]->(fs:Substation)
RETURN d.id AS dispatcher, d.shift AS shift, managed,
       count(f) AS forecastsUsed, collect(DISTINCT fs.id) AS forecastTargets
ORDER BY dispatcher;
