// Q9 · АНАЛІЗ ВПЛИВУ №1 (глибина ≥ 3): що зачепить аварія на підстанції?
// Ланцюг: Substation -FEEDS*0..5-> Substation <-CONNECTED_TO- Consumer, + Dispatcher -MANAGES->
// Конструкції: шлях змінної довжини, min(length) як глибина, OPTIONAL MATCH, агрегації
MATCH p = (root:Substation {id: $substation})-[:FEEDS*0..5]->(s:Substation)
WITH s, min(length(p)) AS depth
OPTIONAL MATCH (d:Dispatcher)-[:MANAGES]->(s)
OPTIONAL MATCH (c:Consumer)-[:CONNECTED_TO]->(s)
RETURN depth, s.id AS substation, d.id AS dispatcher,
       count(c) AS consumers, coalesce(sum(c.contractLimit), 0) AS contractLimitKW
ORDER BY depth, substation;
// параметр: :param substation => 'Substation_1'