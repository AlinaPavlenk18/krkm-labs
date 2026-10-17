// ЛР9 · Результат 2 · Крок 3. Імпорт вузлів. 

LOAD CSV WITH HEADERS FROM 'file:///nodes_consumer.csv' AS row
MERGE (c:Consumer {id: row.id})
SET c.name = row.name, c.category = row.category, c.contractLimit = toFloat(row.contractLimit),
    c.address = row.address, c.source = row.source
FOREACH (_ IN CASE WHEN row.subLabel = 'Residential' THEN [1] ELSE [] END | SET c:Residential)
FOREACH (_ IN CASE WHEN row.subLabel = 'Commercial'  THEN [1] ELSE [] END | SET c:Commercial)
FOREACH (_ IN CASE WHEN row.subLabel = 'Industrial'  THEN [1] ELSE [] END | SET c:Industrial);

LOAD CSV WITH HEADERS FROM 'file:///nodes_meter.csv' AS row
MERGE (m:Meter {id: row.id})
SET m.name = row.name, m.status = row.status, m.meterType = row.meterType,
    m.readingInterval = toInteger(row.readingInterval), m.source = row.source;

LOAD CSV WITH HEADERS FROM 'file:///nodes_measurement.csv' AS row
MERGE (x:Measurement {id: row.id})
SET x.name = row.name, x.consumptionValue = toFloat(row.consumptionValue), x.voltage = toFloat(row.voltage),
    x.timestamp = localdatetime(row.timestamp), x.source = row.source;

LOAD CSV WITH HEADERS FROM 'file:///nodes_weathercondition.csv' AS row
MERGE (w:WeatherCondition {id: row.id})
SET w.name = row.name, w.temperature = toFloat(row.temperature), w.cloudCover = row.cloudCover, w.source = row.source;

LOAD CSV WITH HEADERS FROM 'file:///nodes_forecastmodel.csv' AS row
MERGE (fm:ForecastModel {id: row.id})
SET fm.name = row.name, fm.modelType = row.modelType, fm.accuracy = toFloat(row.accuracy),
    fm.trainingDate = date(row.trainingDate), fm.source = row.source
FOREACH (_ IN CASE WHEN row.subLabel = 'MLModel'          THEN [1] ELSE [] END | SET fm:MLModel)
FOREACH (_ IN CASE WHEN row.subLabel = 'StatisticalModel' THEN [1] ELSE [] END | SET fm:StatisticalModel);

LOAD CSV WITH HEADERS FROM 'file:///nodes_forecast.csv' AS row
MERGE (f:Forecast {id: row.id})
SET f.name = row.name, f.forecastPeriod = row.forecastPeriod, f.errorPercentage = toFloat(row.errorPercentage),
    f.predictedConsumption = toFloat(row.predictedConsumption), f.source = row.source;

LOAD CSV WITH HEADERS FROM 'file:///nodes_dispatcher.csv' AS row
MERGE (d:Dispatcher {id: row.id})
SET d.name = row.name, d.qualification = row.qualification, d.shift = row.shift, d.source = row.source;

LOAD CSV WITH HEADERS FROM 'file:///nodes_substation.csv' AS row
MERGE (s:Substation {id: row.id})
SET s.name = row.name, s.nominalCapacity = toFloat(row.nominalCapacity),
    s.currentLoad = toFloat(row.currentLoad), s.source = row.source;

LOAD CSV WITH HEADERS FROM 'file:///nodes_region.csv' AS row
MERGE (r:Region {id: row.id})
SET r.name = row.name, r.source = row.source;
