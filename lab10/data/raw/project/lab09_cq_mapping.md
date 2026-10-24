# Результат 1. Графова схема під компетентнісні питання

Артефакти: `docs/graph_schema.drawio` (редагована діаграма draw.io), `docs/graph_schema.png`, цей файл.

## 1. Схема LPG

| Мітка | Ключові властивості | Додаткові мітки | К-сть вузлів |
|---|---|---|---|
| `:Consumer` | id (UNIQUE), category (idx), contractLimit, address | `:Residential`, `:Commercial`, `:Industrial` | 41 |
| `:Meter` | id (UNIQUE), status (idx), meterType, readingInterval | — | 43 |
| `:Measurement` | id (UNIQUE), timestamp (idx, Р4), consumptionValue, voltage | — | 48 |
| `:WeatherCondition` | id (UNIQUE), temperature, cloudCover | — | 10 |
| `:ForecastModel` | id (UNIQUE), modelType, accuracy, trainingDate | `:MLModel`, `:StatisticalModel` | 6 |
| `:Forecast` | id (UNIQUE), errorPercentage (idx), predictedConsumption, forecastPeriod | — | 18 |
| `:Dispatcher` | id (UNIQUE), qualification, shift | — | 6 |
| `:Substation` | id (UNIQUE), nominalCapacity, currentLoad | — | 12 |
| `:Region` | id (UNIQUE), name | — | 6 |
| **Разом** | **9 основних міток (+5 додаткових)** | | **190** |

| Тип зв'язку | Напрям | Предикат онтології | К-сть |
|---|---|---|---|
| `HAS_METER` | Consumer → Meter | hasMeter / belongsToConsumer | 43 |
| `CONNECTED_TO` | Consumer → Substation | connectedToSubstation / servesConsumer | 41 |
| `RECORDED` | Meter → Measurement | generatesMeasurement / measuredByMeter | 48 |
| `INFLUENCES` | WeatherCondition → Measurement | influencesMeasurement | 48 |
| `AFFECTS_MODEL` | WeatherCondition → ForecastModel | influencesModel | 10 |
| `TRAINED_ON` | ForecastModel → Measurement | trainedOnMeasurement / measurementUsedForTraining | 37 |
| `GENERATED` | ForecastModel → Forecast | generatesForecast / generatedByModel | 18 |
| `USES_FORECAST` | Dispatcher → Forecast | usesForecast / forecastUsedBy | 18 |
| `MANAGES` | Dispatcher → Substation | managesSubstation / managedByDispatcher | 11 |
| `FEEDS` | Substation → Substation | upstreamOf / downstreamOf (transitive) | 10 |
| `LOCATED_IN` | Substation → Region | (data property `region`) | 12 |
| `FORECAST_FOR` | Forecast → Substation | **нове** forecastForSubstation | 18 |
| **Разом** | **12 типів** | | **314** |

## 2. CQ → шаблони шляхів Cypher

| CQ | Питання | Шаблон шляху | Запит |
|---|---|---|---|
| KQ1 | Які споживачі підключені до підстанції і яка в них категорія? | `(c:Consumer)-[:CONNECTED_TO]->(s:Substation {id:$id})`, `(c)-[:HAS_METER]->(m)` | Q1 |
| KQ2 | Які підстанції перевантажені (≥ 85 %) і хто ними керує? | `(s:Substation) WHERE s.currentLoad/s.nominalCapacity >= 0.85`, `OPTIONAL (d:Dispatcher)-[:MANAGES]->(s)` | Q2 |
| KQ3 | Сумарне навантаження підстанцій за регіонами | `(s:Substation)-[:LOCATED_IN]->(r:Region)` + `sum()` | Q3 |
| KQ4 | Несправні лічильники та їхні власники | `(c:Consumer)-[:HAS_METER]->(m:Meter {status:'несправний'})-[:RECORDED]->(x)` | Q4, Q8 |
| KQ5 | Точність і тип моделі, що згенерувала прогноз | `(fm:ForecastModel)-[:GENERATED]->(f:Forecast)` | Q5 |
| KQ6 | Прогноз із найбільшою похибкою і його модель | `(fm)-[:GENERATED]->(f) ORDER BY f.errorPercentage DESC LIMIT 1` | Q5 |
| KQ7 | Погода, що впливала на вимірювання для навчання моделі | `(fm)-[:TRAINED_ON]->(x:Measurement)<-[:INFLUENCES]-(w:WeatherCondition)` | Q6 |
| KQ8 | Хто з диспетчерів використовує який прогноз і якою підстанцією керує | `(d)-[:USES_FORECAST]->(f)-[:FORECAST_FOR]->(s)`, `(d)-[:MANAGES]->(s)` | Q7 |
| KQ9 (нове) | Що зачепить аварія на підстанції? | `(root:Substation)-[:FEEDS*0..5]->(s)<-[:CONNECTED_TO]-(c)` | Q9 |
| KQ10 (нове) | Які прогнози скомпрометовані даними несправних лічильників? | `(m:Meter)-[:RECORDED]->(x)<-[:TRAINED_ON]-(fm)-[:GENERATED]->(f)<-[:USES_FORECAST]-(d)` | Q10 |

## 3. Властивості походження на зв'язках

Кожен зв'язок має три властивості, перенесені з колонок `triples_final.csv`:

| Властивість | Тип | Значення |
|---|---|---|
| `source` | STRING | `lab08:data.ttl` (твердження з ABox ЛР8), `synthetic:gen_v1(seed=42)` (синтетичне розширення), `derived:lab09(...)` (виведено під час перетворення, напр. регіон) |
| `confidence` | FLOAT 0..1 | 1.0 — облікові факти (належність лічильника, підключення, керування); 0.95 — FORECAST_FOR; 0.55–0.95 — статистичні оцінки впливу погоди (INFLUENCES, AFFECTS_MODEL) |
| `validFrom` | DATE | дата набуття чинності (підключення, призначення диспетчера, дата навчання/прогнозу); для фактів ЛР8 — 2026-09-24 |

Приклад використання: `MATCH (w)-[i:INFLUENCES]->(x) WHERE i.confidence >= 0.8 ...`; `MATCH ()-[r]->() RETURN r.source, count(*)`.

## 4. Порівняння зі схемою (онтологією) ЛР7

| № | Елемент онтології ЛР7 | Рішення в LPG ЛР9 | Обґрунтування |
|---|---|---|---|
| 1 | 8 базових класів (Consumer, Meter, Measurement, WeatherCondition, ForecastModel, Forecast, Dispatcher, Substation) | **мітки** вузлів | сутності з ідентичністю й зв'язками |
| 2 | Підкласи ResidentialConsumer / CommercialConsumer / IndustrialConsumer | **додаткові мітки** `:Residential` тощо + властивість `category` | у LPG немає ієрархії класів; вузол несе кілька міток, тож «виведення підкласу» робимо під час імпорту |
| 3 | Підкласи StatisticalModel / MachineLearningModel | додаткові мітки `:StatisticalModel` / `:MLModel` | те саме |
| 4 | Data property `region` (рядок) | **окремий вузол** `:Region` + `LOCATED_IN` | регіон — спільна точка групування (KQ3) і спільнот Louvain |
| 5 | Datatype properties (currentLoad, accuracy, status…) | **властивості вузлів** | атомарні значення |
| 6 | Обернені пари object properties (hasMeter/belongsToConsumer тощо, 9 пар) | **один напрямлений зв'язок** | у Cypher зв'язок обходиться в обидва боки, тож обернена властивість не потрібна |
| 7 | Транзитивна upstreamOf | `FEEDS` + шлях змінної довжини `[:FEEDS*1..]` | транзитивність виражається в запиті, а не в моделі |
| 8 | Виведений клас ManagedSubstation (`managedByDispatcher some Dispatcher`) | **не матеріалізується**; шаблон `(s)<-[:MANAGES]-()` | LPG не має reasoner'а; умова перевіряється запитом |
| 9 | OverloadedSubstation (ЛР8, через SPARQL UPDATE) | обчислювана умова `currentLoad/nominalCapacity >= 0.85` (Q2) | без дублювання даних; за потреби — `SET s:Overloaded` |
| 10 | Кардинальності (Consumer hasMeter min 1; Forecast/Measurement exactly 1) | перевірочні запити `05_checks.cypher` (5.5); UNIQUE-обмеження на id | у Neo4j немає обмежень кардинальності зв'язків |
| 11 | skos:prefLabel | властивість `name` | — |
| 12 | Вирівнювання із FOAF/schema.org/PROV-O (ЛР8) | **не переноситься** | у LPG немає глобальних IRI; зв'язок зі словниками лишається в RDF-шарі |
| 13 | — (немає в ЛР7) | новий зв'язок `FORECAST_FOR` | потрібен для аналізу впливу (Q9, Q10) |
| 14 | — | властивості походження на зв'язках | у RDF потребували б реифікації/RDF-star |
