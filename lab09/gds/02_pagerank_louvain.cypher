// ЛР9 · Кроки 1 і 4. PageRank і Louvain: перегляд (stream) і збереження у граф (write).

// 2.1 PageRank — топ-10 вузлів
CALL gds.pageRank.stream('energy', {maxIterations: 20, dampingFactor: 0.85})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS n, score
RETURN n.id AS id, labels(n)[0] AS label, n.name AS name, round(score, 4) AS pagerank
ORDER BY pagerank DESC LIMIT 10;

// 2.2 Louvain — розміри спільнот (concurrency: 1 — для відтворюваності результату)
CALL gds.louvain.stream('energy', {concurrency: 1})
YIELD nodeId, communityId
WITH communityId, collect(gds.util.asNode(nodeId)) AS members
RETURN communityId, size(members) AS size,
       [m IN members WHERE m:Substation | m.id] AS substations,
       [m IN members WHERE m:Dispatcher | m.id] AS dispatchers,
       [m IN members WHERE m:ForecastModel | m.id] AS models
ORDER BY size DESC;

// 2.3 Крок 4 — збереження результатів як властивостей вузлів
CALL gds.pageRank.write('energy', {maxIterations: 20, dampingFactor: 0.85, writeProperty: 'pagerank'})
YIELD nodePropertiesWritten, ranIterations;
CALL gds.louvain.write('energy', {concurrency: 1, writeProperty: 'community'})
YIELD communityCount, modularity, nodePropertiesWritten;

// 2.4 Перевірка, що властивості збережено в базі (а не лише в проєкції)
MATCH (n) WHERE n.pagerank IS NOT NULL AND n.community IS NOT NULL
RETURN count(n) AS nodesWithScores;                      

// 2.5 Використання збережених властивостей у звичайному Cypher: найважливіший вузол кожної спільноти
MATCH (n) WITH n.community AS community, n ORDER BY n.pagerank DESC
WITH community, collect(n)[0] AS hub, count(*) AS size
RETURN community, size, hub.id AS hub, labels(hub)[0] AS hubLabel, round(hub.pagerank, 3) AS hubPagerank
ORDER BY size DESC;
