// ЛР9 · Результат 2 · Крок 3. Імпорт зв'язків із властивостями походження (source, confidence, validFrom).

LOAD CSV WITH HEADERS FROM 'file:///rels_has_meter.csv' AS row
MATCH (a:Consumer {id: row.start})
MATCH (b:Meter {id: row.end})
MERGE (a)-[r:HAS_METER]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_connected_to.csv' AS row
MATCH (a:Consumer {id: row.start})
MATCH (b:Substation {id: row.end})
MERGE (a)-[r:CONNECTED_TO]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_recorded.csv' AS row
MATCH (a:Meter {id: row.start})
MATCH (b:Measurement {id: row.end})
MERGE (a)-[r:RECORDED]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_influences.csv' AS row
MATCH (a:WeatherCondition {id: row.start})
MATCH (b:Measurement {id: row.end})
MERGE (a)-[r:INFLUENCES]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_affects_model.csv' AS row
MATCH (a:WeatherCondition {id: row.start})
MATCH (b:ForecastModel {id: row.end})
MERGE (a)-[r:AFFECTS_MODEL]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_trained_on.csv' AS row
MATCH (a:ForecastModel {id: row.start})
MATCH (b:Measurement {id: row.end})
MERGE (a)-[r:TRAINED_ON]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_generated.csv' AS row
MATCH (a:ForecastModel {id: row.start})
MATCH (b:Forecast {id: row.end})
MERGE (a)-[r:GENERATED]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_uses_forecast.csv' AS row
MATCH (a:Dispatcher {id: row.start})
MATCH (b:Forecast {id: row.end})
MERGE (a)-[r:USES_FORECAST]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_manages.csv' AS row
MATCH (a:Dispatcher {id: row.start})
MATCH (b:Substation {id: row.end})
MERGE (a)-[r:MANAGES]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_feeds.csv' AS row
MATCH (a:Substation {id: row.start})
MATCH (b:Substation {id: row.end})
MERGE (a)-[r:FEEDS]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_located_in.csv' AS row
MATCH (a:Substation {id: row.start})
MATCH (b:Region {id: row.end})
MERGE (a)-[r:LOCATED_IN]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;

LOAD CSV WITH HEADERS FROM 'file:///rels_forecast_for.csv' AS row
MATCH (a:Forecast {id: row.start})
MATCH (b:Substation {id: row.end})
MERGE (a)-[r:FORECAST_FOR]->(b)
SET r.source = row.source,
    r.confidence = toFloat(row.confidence),
    r.validFrom = CASE WHEN row.validFrom IS NULL OR row.validFrom = '' THEN null ELSE date(row.validFrom) END;
