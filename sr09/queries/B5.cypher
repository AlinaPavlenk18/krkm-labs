// B5 · Ланцюг глибини 4: прогнози, скомпрометовані несправними лічильниками
MATCH (m:Meter {status: 'несправний'})-[:RECORDED]->(x:Measurement)<-[:TRAINED_ON]-(fm:ForecastModel)-[:GENERATED]->(f:Forecast)<-[:USES_FORECAST]-(d:Dispatcher)
RETURN fm.id AS model, count(DISTINCT f) AS forecasts, count(DISTINCT d) AS dispatchers
ORDER BY model;
