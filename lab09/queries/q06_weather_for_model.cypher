// Q6 · KQ7: Які погодні умови впливали на вимірювання, на яких навчено задану модель?
// Конструкції: двоколовий шаблон шляху зі зустрічними напрямками, змінна зв'язку (властивість confidence), агрегація
MATCH (fm:ForecastModel {id: $model})-[:TRAINED_ON]->(x:Measurement)<-[i:INFLUENCES]-(w:WeatherCondition)
RETURN w.id AS weather, w.temperature AS temperature, w.cloudCover AS cloudCover,
       count(x) AS measurements, round(avg(i.confidence), 2) AS avgConfidence
ORDER BY temperature;
// параметр: :param model => 'ForecastModel_LSTM2'
