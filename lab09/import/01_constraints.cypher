// ЛР9 · Результат 2 · Крок 2. Унікальні обмеження (кожне автоматично створює індекс-опору).
CREATE CONSTRAINT consumer_id    IF NOT EXISTS FOR (n:Consumer)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT meter_id       IF NOT EXISTS FOR (n:Meter)            REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT measurement_id IF NOT EXISTS FOR (n:Measurement)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT weather_id     IF NOT EXISTS FOR (n:WeatherCondition) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT model_id       IF NOT EXISTS FOR (n:ForecastModel)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT forecast_id    IF NOT EXISTS FOR (n:Forecast)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dispatcher_id  IF NOT EXISTS FOR (n:Dispatcher)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT substation_id  IF NOT EXISTS FOR (n:Substation)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT region_id      IF NOT EXISTS FOR (n:Region)           REQUIRE n.id IS UNIQUE;
