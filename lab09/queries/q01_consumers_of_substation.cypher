// Q1 · KQ1: Які споживачі підключені до заданої підстанції і яка в кожного категорія?
// Конструкції: MATCH з фільтром за властивістю, OPTIONAL MATCH, агрегація collect, ORDER BY
MATCH (c:Consumer)-[:CONNECTED_TO]->(s:Substation {id: $substation})
OPTIONAL MATCH (c)-[:HAS_METER]->(m:Meter)
RETURN c.id AS consumer, c.category AS category, c.contractLimit AS contractLimit,
       collect(m.id) AS meters
ORDER BY contractLimit DESC;
// параметр: :param substation => 'Substation_7'
