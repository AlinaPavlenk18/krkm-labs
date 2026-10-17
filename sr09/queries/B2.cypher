// B2 · Агрегація: кількість, потужність і навантаження підстанцій за регіонами
MATCH (s:Substation)-[:LOCATED_IN]->(r:Region)
RETURN r.name AS region, count(s) AS substations, sum(s.nominalCapacity) AS capacity, sum(s.currentLoad) AS load
ORDER BY region;
