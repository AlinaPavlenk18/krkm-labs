// Q2 · KQ2: Які підстанції перевантажені (навантаження ≥ 85 % номіналу) і хто ними керує?
// Конструкції: WHERE з обчисленим виразом, OPTIONAL MATCH (диспетчера може не бути), round
MATCH (s:Substation)
WHERE s.currentLoad / s.nominalCapacity >= 0.85
OPTIONAL MATCH (d:Dispatcher)-[:MANAGES]->(s)
RETURN s.id AS substation, s.currentLoad AS load, s.nominalCapacity AS capacity,
       round(100.0 * s.currentLoad / s.nominalCapacity, 1) AS loadPct, d.id AS dispatcher
ORDER BY loadPct DESC;
