// B1 · Фільтр + OPTIONAL: перевантажені підстанції (≥ 85 %) і диспетчер
// Однаковий текст для Neo4j і Memgraph
MATCH (s:Substation)
WHERE s.currentLoad >= 0.85 * s.nominalCapacity
OPTIONAL MATCH (d:Dispatcher)-[:MANAGES]->(s)
RETURN s.id AS substation, s.currentLoad / s.nominalCapacity AS ratio, d.id AS dispatcher
ORDER BY substation;
