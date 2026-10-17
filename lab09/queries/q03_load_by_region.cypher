// Q3 · KQ3: Яке сумарне номінальне навантаження підстанцій у кожному регіоні?
// Конструкції: агрегації count/sum, обчислення на агрегатах, ORDER BY
MATCH (s:Substation)-[:LOCATED_IN]->(r:Region)
RETURN r.name AS region, count(s) AS substations,
       sum(s.nominalCapacity) AS totalCapacity, sum(s.currentLoad) AS totalLoad,
       round(100.0 * sum(s.currentLoad) / sum(s.nominalCapacity), 1) AS loadPct
ORDER BY totalCapacity DESC;
