// Ручна перевірка (Результат 3, крок 4): ті самі запити на МАЛОМУ підграфі — лише вузли з ЛР8
// (source = 'lab08:data.ttl', 25 вузлів). Результати порівнюються з ручним розрахунком за data.ttl.

// M1 (= Q2 на підграфі): перевантажені підстанції
MATCH (s:Substation) WHERE s.source = 'lab08:data.ttl' AND s.currentLoad / s.nominalCapacity >= 0.85
OPTIONAL MATCH (d:Dispatcher)-[:MANAGES]->(s) WHERE d.source = 'lab08:data.ttl'
RETURN s.id AS substation, round(100.0 * s.currentLoad / s.nominalCapacity, 1) AS loadPct, d.id AS dispatcher
ORDER BY loadPct DESC;

// M2 (= Q9 на підграфі): аварія на підстанції №7
MATCH p = (root:Substation {id: 'Substation_7'})-[:FEEDS*0..5]->(s:Substation)
WHERE all(n IN nodes(p) WHERE n.source = 'lab08:data.ttl')
WITH s, min(length(p)) AS depth
OPTIONAL MATCH (c:Consumer)-[:CONNECTED_TO]->(s) WHERE c.source = 'lab08:data.ttl'
RETURN depth, s.id AS substation, collect(c.id) AS consumers, coalesce(sum(c.contractLimit), 0) AS contractLimitKW
ORDER BY depth;

// M3 (= Q10 на підграфі): прогнози, скомпрометовані несправними лічильниками
MATCH p = (m:Meter {status: 'несправний'})-[:RECORDED]->(x:Measurement)<-[:TRAINED_ON]-(fm:ForecastModel)
          -[:GENERATED]->(f:Forecast)<-[:USES_FORECAST]-(d:Dispatcher)
WHERE all(n IN nodes(p) WHERE n.source = 'lab08:data.ttl')
RETURN m.id AS meter, x.id AS measurement, fm.id AS model, f.id AS forecast, f.errorPercentage AS error, d.id AS dispatcher;
