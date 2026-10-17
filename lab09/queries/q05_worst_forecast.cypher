// Q5 · KQ5 + KQ6: Який прогноз має найбільшу похибку, яка модель його згенерувала і яка її середня похибка?
// Конструкції: WITH ... ORDER BY ... LIMIT (top-1 посеред запиту), повторний MATCH, avg/count
MATCH (fm:ForecastModel)-[:GENERATED]->(f:Forecast)
WITH fm, f ORDER BY f.errorPercentage DESC LIMIT 1
MATCH (fm)-[:GENERATED]->(other:Forecast)
RETURN f.id AS forecast, f.errorPercentage AS error, fm.id AS model, fm.modelType AS type,
       fm.accuracy AS accuracy, fm.trainingDate AS trainingDate,
       count(other) AS modelForecasts, round(avg(other.errorPercentage), 2) AS modelAvgError;
