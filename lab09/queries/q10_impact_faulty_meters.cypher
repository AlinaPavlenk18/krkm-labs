// Q10 · АНАЛІЗ ВПЛИВУ №2 (глибина 4): які прогнози й диспетчери «скомпрометовані» даними несправних лічильників?
// Ланцюг: Meter(несправний) -RECORDED-> Measurement <-TRAINED_ON- ForecastModel -GENERATED-> Forecast <-USES_FORECAST- Dispatcher
// Конструкції: довгий шаблон шляху, WITH, collect DISTINCT, count DISTINCT
MATCH (m:Meter {status: 'несправний'})-[:RECORDED]->(x:Measurement)<-[:TRAINED_ON]-(fm:ForecastModel)
WITH fm, collect(DISTINCT m.id) AS faultyMeters, count(DISTINCT x) AS badMeasurements
MATCH (fm)-[:GENERATED]->(f:Forecast)<-[:USES_FORECAST]-(d:Dispatcher)
RETURN fm.id AS model, faultyMeters, badMeasurements,
       count(DISTINCT f) AS affectedForecasts, collect(DISTINCT d.id) AS dispatchersToNotify
ORDER BY badMeasurements DESC, model;
