// B4 · Транзитивний обхід: зона впливу аварії на кореневій ПС №1 і споживачі в ній
MATCH (root:Substation {id: 'Substation_1'})
OPTIONAL MATCH (root)-[:FEEDS*1..10]->(d:Substation)
WITH root, collect(DISTINCT d) AS down
UNWIND [root] + down AS s
OPTIONAL MATCH (c:Consumer)-[:CONNECTED_TO]->(s)
RETURN s.id AS substation, count(c) AS consumers
ORDER BY substation;
