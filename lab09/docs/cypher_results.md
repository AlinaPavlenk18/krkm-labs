# Результат 3. Запити Cypher: CQ, запит, результат, інтерпретація

Очікувані результати отримано виконанням запитів у вбудованій графовій БД Kùzu 0.11 на тих самих CSV (`scripts/verify_kuzu.py`). Після запуску в Neo4j значення мають збігтися; порядок елементів усередині списків `collect()` може відрізнятися.

Граф: **190 вузлів, 314 зв'язків**.

## Q01 · KQ1

**Конструкції:** MATCH + фільтр за властивістю, OPTIONAL MATCH, collect, ORDER BY. **Параметри:** $substation = 'Substation_7'

```cypher
// Q1 · KQ1: Які споживачі підключені до заданої підстанції і яка в кожного категорія?
// Конструкції: MATCH з фільтром за властивістю, OPTIONAL MATCH, агрегація collect, ORDER BY
MATCH (c:Consumer)-[:CONNECTED_TO]->(s:Substation {id: $substation})
OPTIONAL MATCH (c)-[:HAS_METER]->(m:Meter)
RETURN c.id AS consumer, c.category AS category, c.contractLimit AS contractLimit,
       collect(m.id) AS meters
ORDER BY contractLimit DESC;
```

**Результат:**

| consumer | category | contractLimit | meters |
|---|---|---|---|
| Consumer_4521 | промисловий | 450.0 | Meter_AMI99231, Meter_AMI81841 |
| Consumer_5021 | комерційний | 124.7 | Meter_AMI55149 |
| Consumer_5010 | комерційний | 67.4 | Meter_AMI36309 |
| Consumer_5032 | побутовий | 11.6 | Meter_AMI69457 |

**Інтерпретація.** До підстанції №7 підключено 4 споживачі. Найбільший договірний ліміт має промисловий споживач №4521 (450 кВт), і лише в нього два лічильники: основний AMI-99231 і резервний. Отже, від стану ПС №7 найбільше залежить саме промислове навантаження.

## Q02 · KQ2

**Конструкції:** WHERE з обчисленим виразом, OPTIONAL MATCH, round. **Параметри:** —

```cypher
// Q2 · KQ2: Які підстанції перевантажені (навантаження ≥ 85 % номіналу) і хто ними керує?
// Конструкції: WHERE з обчисленим виразом, OPTIONAL MATCH (диспетчера може не бути), round
MATCH (s:Substation)
WHERE s.currentLoad / s.nominalCapacity >= 0.85
OPTIONAL MATCH (d:Dispatcher)-[:MANAGES]->(s)
RETURN s.id AS substation, s.currentLoad AS load, s.nominalCapacity AS capacity,
       round(100.0 * s.currentLoad / s.nominalCapacity, 1) AS loadPct, d.id AS dispatcher
ORDER BY loadPct DESC;
```

**Результат:**

| substation | load | capacity | loadPct | dispatcher |
|---|---|---|---|---|
| Substation_5 | 468.0 | 500.0 | 93.6 | Dispatcher_3 |
| Substation_4 | 450.0 | 500.0 | 90.0 | Dispatcher_6 |
| Substation_7 | 870.0 | 1000.0 | 87.0 | Dispatcher_1 |
| Substation_11 | 301.0 | 350.0 | 86.0 | Dispatcher_2 |

**Інтерпретація.** Перевантажені 4 підстанції з 12. Найгірша — №5 (93,6 %). Дві з них (№5 і №7) були перевантажені вже в ЛР7–8, ще дві (№4 і №11) з'явилися в розширених даних. У кожної перевантаженої підстанції є відповідальний диспетчер, отже, сповіщення можна адресувати конкретній людині.

## Q03 · KQ3

**Конструкції:** агрегації count/sum, обчислення на агрегатах. **Параметри:** —

```cypher
// Q3 · KQ3: Яке сумарне номінальне навантаження підстанцій у кожному регіоні?
// Конструкції: агрегації count/sum, обчислення на агрегатах, ORDER BY
MATCH (s:Substation)-[:LOCATED_IN]->(r:Region)
RETURN r.name AS region, count(s) AS substations,
       sum(s.nominalCapacity) AS totalCapacity, sum(s.currentLoad) AS totalLoad,
       round(100.0 * sum(s.currentLoad) / sum(s.nominalCapacity), 1) AS loadPct
ORDER BY totalCapacity DESC;
```

**Результат:**

| region | substations | totalCapacity | totalLoad | loadPct |
|---|---|---|---|---|
| Львівська область | 4 | 4950.0 | 3590.0 | 72.5 |
| Волинська область | 2 | 1300.0 | 980.0 | 75.4 |
| Рівненська область | 2 | 950.0 | 703.0 | 74.0 |
| Закарпатська область | 2 | 700.0 | 261.0 | 37.3 |
| Тернопільська область | 1 | 500.0 | 450.0 | 90.0 |
| Івано-Франківська область | 1 | 400.0 | 236.0 | 59.0 |

**Інтерпретація.** Найбільша сумарна потужність у Львівській області (4950 кВт, 4 підстанції), але найвище відносне навантаження в Тернопільській (90 %): там лише одна підстанція, і вона перевантажена. Закарпаття завантажене найменше (37,3 %), тож має резерв для перерозподілу.

## Q04 · KQ4

**Конструкції:** фільтр за індексованою властивістю, OPTIONAL MATCH, WITH + ORDER BY + collect()[0]. **Параметри:** —

```cypher
// Q4 · KQ4: Які лічильники мають статус «несправний», яким споживачам належать і яке останнє вимірювання?
// Конструкції: фільтр за індексованою властивістю (meter_status), OPTIONAL MATCH, WITH + ORDER BY + collect()[0]
MATCH (c:Consumer)-[:HAS_METER]->(m:Meter {status: 'несправний'})
OPTIONAL MATCH (m)-[:RECORDED]->(x:Measurement)
WITH c, m, x ORDER BY x.timestamp DESC
WITH c, m, collect(x)[0] AS last
MATCH (c)-[:CONNECTED_TO]->(s:Substation)
RETURN m.id AS meter, c.id AS consumer, c.category AS category, s.id AS substation,
       last.voltage AS lastVoltage, last.timestamp AS lastTimestamp
ORDER BY meter;
```

**Результат:**

| meter | consumer | category | substation | lastVoltage | lastTimestamp |
|---|---|---|---|---|---|
| Meter_AMI26032 | Consumer_5004 | побутовий | Substation_6 | 209.0 | 2026-09-29T08:00:00 |
| Meter_AMI27192 | Consumer_5005 | комерційний | Substation_8 | 197.6 | 2026-09-30T08:00:00 |
| Meter_AMI66829 | Consumer_5030 | побутовий | Substation_12 | 205.3 | 2026-09-27T18:00:00 |
| Meter_AMI71354 | Consumer_5034 | побутовий | Substation_2 | 204.6 | 2026-01-11T18:00:00 |
| Meter_AMI77410 | Consumer_3310 | комерційний | Substation_5 | 233.0 | 2026-01-10T08:00:00 |

**Інтерпретація.** Несправних лічильників 5. У чотирьох синтетичних останнє вимірювання має занижену напругу (197–209 В проти норми ≈ 230 В). Це узгоджується зі статусом і може бути ознакою несправності. Лічильник AMI-77410 з ЛР8 показав 233 В, тобто його несправність напругою не пояснюється.

## Q05 · KQ5, KQ6

**Конструкції:** WITH … ORDER BY … LIMIT посеред запиту, повторний MATCH, avg/count. **Параметри:** —

```cypher
// Q5 · KQ5 + KQ6: Який прогноз має найбільшу похибку, яка модель його згенерувала і яка її середня похибка?
// Конструкції: WITH ... ORDER BY ... LIMIT (top-1 посеред запиту), повторний MATCH, avg/count
MATCH (fm:ForecastModel)-[:GENERATED]->(f:Forecast)
WITH fm, f ORDER BY f.errorPercentage DESC LIMIT 1
MATCH (fm)-[:GENERATED]->(other:Forecast)
RETURN f.id AS forecast, f.errorPercentage AS error, fm.id AS model, fm.modelType AS type,
       fm.accuracy AS accuracy, fm.trainingDate AS trainingDate,
       count(other) AS modelForecasts, round(avg(other.errorPercentage), 2) AS modelAvgError;
```

**Результат:**

| forecast | error | model | type | accuracy | trainingDate | modelForecasts | modelAvgError |
|---|---|---|---|---|---|---|---|
| Forecast_20261004_2 | 12.3 | ForecastModel_LSTM2 | LSTM | 78.0 | 2025-06-20 | 3 | 11.23 |

**Інтерпретація.** Найбільша похибка (12,3 %) у прогнозі моделі LSTM №2. Ця модель має найнижчу точність (78 %), навчена найраніше (2025-06-20), і середня похибка всіх трьох її прогнозів 11,23 %. Висновок ЛР7 підтверджується: LSTM №2 — кандидат на перенавчання.

## Q06 · KQ7

**Конструкції:** двосегментний шаблон зі зустрічними напрямками, змінна зв'язку (confidence), агрегація. **Параметри:** $model = 'ForecastModel_LSTM2'

```cypher
// Q6 · KQ7: Які погодні умови впливали на вимірювання, на яких навчено задану модель?
// Конструкції: двоколовий шаблон шляху зі зустрічними напрямками, змінна зв'язку (властивість confidence), агрегація
MATCH (fm:ForecastModel {id: $model})-[:TRAINED_ON]->(x:Measurement)<-[i:INFLUENCES]-(w:WeatherCondition)
RETURN w.id AS weather, w.temperature AS temperature, w.cloudCover AS cloudCover,
       count(x) AS measurements, round(avg(i.confidence), 2) AS avgConfidence
ORDER BY temperature;
```

**Результат:**

| weather | temperature | cloudCover | measurements | avgConfidence |
|---|---|---|---|---|
| WeatherCondition_20260111 | -15.5 | суцільна | 2 | 0.83 |
| WeatherCondition_20260110 | -12.0 | суцільна | 1 | 1.0 |
| WeatherCondition_20260112 | -9.0 | мінлива | 2 | 0.73 |

**Інтерпретація.** LSTM №2 навчена лише на зимових вимірюваннях: 10–12 січня, від −15,5 до −9 °C. Це пояснює великі похибки її осінніх прогнозів: погодні умови навчальної вибірки не репрезентативні для сезону, для якого вона прогнозує.

## Q07 · KQ8

**Конструкції:** два OPTIONAL MATCH, розділені WITH, collect DISTINCT. **Параметри:** —

```cypher
// Q7 · KQ8: Який диспетчер використовує які прогнози і якими підстанціями він керує?
// Конструкції: два OPTIONAL MATCH, розділені WITH (уникнення декартового добутку), collect DISTINCT
MATCH (d:Dispatcher)
OPTIONAL MATCH (d)-[:MANAGES]->(s:Substation)
WITH d, collect(s.id) AS managed
OPTIONAL MATCH (d)-[:USES_FORECAST]->(f:Forecast)-[:FORECAST_FOR]->(fs:Substation)
RETURN d.id AS dispatcher, d.shift AS shift, managed,
       count(f) AS forecastsUsed, collect(DISTINCT fs.id) AS forecastTargets
ORDER BY dispatcher;
```

**Результат:**

| dispatcher | shift | managed | forecastsUsed | forecastTargets |
|---|---|---|---|---|
| Dispatcher_1 | ранкова | Substation_7 | 2 | Substation_7 |
| Dispatcher_2 | вечірня | Substation_11, Substation_12 | 4 | Substation_11, Substation_12 |
| Dispatcher_3 | нічна | Substation_5 | 2 | Substation_5 |
| Dispatcher_4 | ранкова | Substation_1, Substation_10 | 4 | Substation_10, Substation_1 |
| Dispatcher_5 | вечірня | Substation_2, Substation_3, Substation_8 | 4 | Substation_2, Substation_8, Substation_3 |
| Dispatcher_6 | нічна | Substation_4, Substation_6 | 2 | Substation_6, Substation_4 |

**Інтерпретація.** Кожен диспетчер використовує прогнози лише для тих підстанцій, якими сам керує, тож розподіл відповідальності узгоджений. Найбільше підстанцій (3) у диспетчера №5. Диспетчери №2, №4 і №5 використовують по 4 прогнози.

## Q08 · KQ4, KQ8

**Конструкції:** shortestPath, шлях змінної довжини з кількома типами, list comprehension. **Параметри:** $meter = 'Meter_AMI77410'

```cypher
// Q8 · KQ4 + KQ8: Через який найкоротший ланцюг мережі несправний лічильник пов'язаний з кожним диспетчером
// (кого сповіщати першим)? Шлях обмежено «інфраструктурними» типами зв'язків.
// Конструкції: shortestPath, шлях змінної довжини з кількома типами, ненапрямлений обхід, list comprehension
MATCH (m:Meter {id: $meter}), (d:Dispatcher)
MATCH p = shortestPath((m)-[:HAS_METER|CONNECTED_TO|FEEDS|MANAGES*..8]-(d))
RETURN d.id AS dispatcher, length(p) AS hops,
       [n IN nodes(p) | n.id] AS path, [r IN relationships(p) | type(r)] AS relTypes
ORDER BY hops, dispatcher;
```

**Результат:**

| dispatcher | hops | path | relTypes |
|---|---|---|---|
| Dispatcher_3 | 3 | Meter_AMI77410, Consumer_3310, Substation_5, Dispatcher_3 | HAS_METER, CONNECTED_TO, MANAGES |
| Dispatcher_1 | 4 | Meter_AMI77410, Consumer_3310, Substation_5, Substation_7, Dispatcher_1 | HAS_METER, CONNECTED_TO, FEEDS, MANAGES |
| Dispatcher_2 | 4 | Meter_AMI77410, Consumer_3310, Substation_5, Substation_12, Dispatcher_2 | HAS_METER, CONNECTED_TO, FEEDS, MANAGES |
| Dispatcher_4 | 5 | Meter_AMI77410, Consumer_3310, Substation_5, Substation_7, Substation_1, Dispatcher_4 | HAS_METER, CONNECTED_TO, FEEDS, FEEDS, MANAGES |
| Dispatcher_5 | 6 | Meter_AMI77410, Consumer_3310, Substation_5, Substation_7, Substation_1, Substation_2, Dispatcher_5 | HAS_METER, CONNECTED_TO, FEEDS, FEEDS, FEEDS, MANAGES |
| Dispatcher_6 | 7 | Meter_AMI77410, Consumer_3310, Substation_5, Substation_7, Substation_1, Substation_10, Substation_4, Dispatcher_6 | HAS_METER, CONNECTED_TO, FEEDS, FEEDS, FEEDS, FEEDS, MANAGES |

**Інтерпретація.** Від несправного лічильника AMI-77410 найближчий диспетчер №3 (3 переходи: лічильник → споживач №3310 → ПС №5 → диспетчер). Інші диспетчери досяжні лише через ланцюг живлення FEEDS. Тому сповіщати слід диспетчера №3, а диспетчера №1 (ПС №7 живить ПС №5) — другим.

## Q09 · Аналіз впливу №1

**Конструкції:** шлях змінної довжини FEEDS*0..5, min(length), OPTIONAL MATCH, агрегації. **Параметри:** $substation = 'Substation_1'

```cypher
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
// Підсумок одним рядком (35 споживачів, 5191.5 кВт):
// MATCH (:Substation {id: $substation})-[:FEEDS*0..5]->(s:Substation)<-[:CONNECTED_TO]-(c:Consumer)
// WITH DISTINCT c RETURN count(c) AS consumers, sum(c.contractLimit) AS contractLimitKW;
```

**Результат:**

| depth | substation | dispatcher | consumers | contractLimitKW |
|---|---|---|---|---|
| 0 | Substation_1 | Dispatcher_4 | 1 | 1500.0 |
| 1 | Substation_10 | Dispatcher_4 | 3 | 483.2 |
| 1 | Substation_2 | Dispatcher_5 | 4 | 917.6 |
| 1 | Substation_7 | Dispatcher_1 | 4 | 653.7 |
| 2 | Substation_3 | Dispatcher_5 | 4 | 534.9 |
| 2 | Substation_4 | Dispatcher_6 | 4 | 39.2 |
| 2 | Substation_5 | Dispatcher_3 | 4 | 517.4 |
| 3 | Substation_11 | Dispatcher_2 | 3 | 124.7 |
| 3 | Substation_12 | Dispatcher_2 | 4 | 381.8 |
| 3 | Substation_6 | Dispatcher_6 | 4 | 39.0 |

**Інтерпретація.** Аварія на магістральній ПС №1 каскадно зачіпає 10 підстанцій до глибини 3 і 35 споживачів із сумарним договірним лімітом 5191,5 кВт. Сповіщати треба всіх 6 диспетчерів. Не зачеплені лише Закарпатські ПС №9 і №8, бо вони живляться окремо. На глибині 2 є перевантажена ПС №4 (90 %).

## Q10 · Аналіз впливу №2

**Конструкції:** довгий шаблон шляху (глибина 4), WITH, collect/count DISTINCT. **Параметри:** —

```cypher
// Q10 · АНАЛІЗ ВПЛИВУ №2 (глибина 4): які прогнози й диспетчери «скомпрометовані» даними несправних лічильників?
// Ланцюг: Meter(несправний) -RECORDED-> Measurement <-TRAINED_ON- ForecastModel -GENERATED-> Forecast <-USES_FORECAST- Dispatcher
// Конструкції: довгий шаблон шляху, WITH, collect DISTINCT, count DISTINCT
MATCH (m:Meter {status: 'несправний'})-[:RECORDED]->(x:Measurement)<-[:TRAINED_ON]-(fm:ForecastModel)
WITH fm, collect(DISTINCT m.id) AS faultyMeters, count(DISTINCT x) AS badMeasurements
MATCH (fm)-[:GENERATED]->(f:Forecast)<-[:USES_FORECAST]-(d:Dispatcher)
RETURN fm.id AS model, faultyMeters, badMeasurements,
       count(DISTINCT f) AS affectedForecasts, collect(DISTINCT d.id) AS dispatchersToNotify
ORDER BY badMeasurements DESC, model;
```

**Результат:**

| model | faultyMeters | badMeasurements | affectedForecasts | dispatchersToNotify |
|---|---|---|---|---|
| ForecastModel_GRU1 | Meter_AMI27192, Meter_AMI66829 | 2 | 4 | Dispatcher_5, Dispatcher_3, Dispatcher_6, Dispatcher_4 |
| ForecastModel_ARIMA1 | Meter_AMI27192 | 1 | 2 | Dispatcher_5 |
| ForecastModel_LSTM2 | Meter_AMI77410 | 1 | 3 | Dispatcher_2, Dispatcher_3 |

**Інтерпретація.** Дані несправних лічильників потрапили в навчальні вибірки трьох моделей (GRU №1, ARIMA №1, LSTM №2). Через них «скомпрометовано» 9 прогнозів, якими користуються 5 диспетчерів. Найбільший вплив має GRU №1 (4 прогнози, 4 диспетчери): її варто перенавчити, вилучивши вимірювання цих лічильників.

## Ручна перевірка на малому підграфі (крок 4)

Запити `queries/q00_manual_check_subgraph.cypher` повторюють Q2, Q9 і Q10, але лише на 25 вузлах ЛР8 (`source = 'lab08:data.ttl'`). Значення порахував вручну за `data/source/lab08_data.ttl`.

| Перевірка | Ручний розрахунок за data.ttl | Результат запиту | Збіг |
|---|---|---|---|
| M1 (= Q2) | ПС №5: 468/500 = 93,6 % ≥ 85 % → Disp_3; ПС №7: 870/1000 = 87 % → Disp_1; ПС №12: 90/250 = 36 %; ПС №9: 120/400 = 30 % | Substation_5 93.6 % (Dispatcher_3); Substation_7 87.0 % (Dispatcher_1) | ✓ |
| M2 (= Q9 від ПС №7) | upstreamOf: 7 → 5 → 12; споживачі: 4521 (450) на №7, 3310 (120) на №5, 1002 (10) на №12 | глибина 0: Substation_7 ['Consumer_4521'] 450.0; глибина 1: Substation_5 ['Consumer_3310'] 120.0; глибина 2: Substation_12 ['Consumer_1002'] 10.0 | ✓ |
| M3 (= Q10) | AMI-77410 (несправний) → Measurement_003 → LSTM2 (trainedOn) → Forecast_20260110 (11 %) → Dispatcher_3 (usesForecast) | Meter_AMI77410 → Measurement_003 → ForecastModel_LSTM2 → Forecast_20260110 (11.0 %) → Dispatcher_3 | ✓ |
