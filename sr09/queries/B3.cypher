// B3 · З'єднання (2 зв'язки): несправні лічильники, власник і підстанція
MATCH (c:Consumer)-[:HAS_METER]->(m:Meter {status: 'несправний'})
MATCH (c)-[:CONNECTED_TO]->(s:Substation)
RETURN m.id AS meter, c.id AS consumer, s.id AS substation
ORDER BY meter;
