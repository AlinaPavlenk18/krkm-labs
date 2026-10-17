// ЛР9 · Результат 2 · Крок 2. Індекси (range) для властивостей, за якими фільтрують запити Cypher.
CREATE INDEX meter_status      IF NOT EXISTS FOR (m:Meter)    ON (m.status);            // KQ4: несправні лічильники
CREATE INDEX consumer_category IF NOT EXISTS FOR (c:Consumer) ON (c.category);          // KQ1: споживачі за категорією
CREATE INDEX forecast_error    IF NOT EXISTS FOR (f:Forecast) ON (f.errorPercentage);   // KQ6: прогнози з великою похибкою
CREATE INDEX feeds_valid_from  IF NOT EXISTS FOR ()-[r:FEEDS]-() ON (r.validFrom);      // індекс на властивості зв'язку
// Індекс measurement_ts (Measurement.timestamp) НАВМИСНО створюється пізніше — у Результаті 4
// (gds/03_profile.cypher), щоб показати PROFILE «до» і «після» оптимізації.
