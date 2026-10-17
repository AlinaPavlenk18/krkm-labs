// Q4 · KQ4: Які лічильники мають статус «несправний», яким споживачам належать і яке останнє вимірювання?
// Конструкції: фільтр за індексованою властивістю (meter_status), OPTIONAL MATCH, WITH + ORDER BY + collect()[0]
MATCH (c:Consumer)-[:HAS_METER]->(m:Meter {status: 'несправний'})
OPTIONAL MATCH (m)-[:RECORDED]->(x:Measurement)
WITH c, m, x ORDER BY x.timestamp DESC
WITH c, m, collect(x)[0] AS last
MATCH (c)-[:CONNECTED_TO]->(s:Substation)
RETURN m.id AS meter, c.id AS consumer, c.category AS category, s.id AS substation,
       last.voltage AS lastVoltage, last.timestamp AS lastTimestamp
ORDER BY meter;
