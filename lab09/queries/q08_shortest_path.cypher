// Q8 · KQ4 + KQ8: Через який найкоротший ланцюг мережі несправний лічильник пов'язаний з кожним диспетчером
// (кого сповіщати першим)? Шлях обмежено «інфраструктурними» типами зв'язків.
// Конструкції: shortestPath, шлях змінної довжини з кількома типами, ненапрямлений обхід, list comprehension
MATCH (m:Meter {id: $meter}), (d:Dispatcher)
MATCH p = shortestPath((m)-[:HAS_METER|CONNECTED_TO|FEEDS|MANAGES*..8]-(d))
RETURN d.id AS dispatcher, length(p) AS hops,
       [n IN nodes(p) | n.id] AS path, [r IN relationships(p) | type(r)] AS relTypes
ORDER BY hops, dispatcher;
// параметр: :param meter => 'Meter_AMI77410'
