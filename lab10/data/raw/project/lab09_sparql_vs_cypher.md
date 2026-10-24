# Результат 5. Порівняння SPARQL і Cypher; text-to-Cypher

## 1. П'ять питань обома мовами

SPARQL — запити 1–5 з ЛР8 без змін, виконані через rdflib 7 над повним набором `triples_final.csv` +
`vocabulary.ttl` з RDFS-виведенням (owlrl). Cypher — ті самі питання над графом із 190 вузлів
(перевірка в Kùzu; у Neo4j виконати `python scripts/compare_sparql_cypher.py --cypher neo4j`, у Fuseki —
`--fuseki http://localhost:3030/energy/sparql`). Скрипт: `scripts/compare_sparql_cypher.py`,
повні результати — `docs/sparql_vs_cypher_results.json`.

| № | Питання | Рядків SPARQL | Рядків Cypher | Результати збігаються | Рядків коду SPARQL / Cypher | Символів SPARQL / Cypher | Медіана часу, мс (rdflib / Kùzu) |
|---|---|---|---|---|---|---|---|
| S1 | Перевантажені підстанції (≥ 85 %) і диспетчер (KQ2, KQ8) | 4 | 4 | так | 10 / 5 | 419 / 281 | 18.07 / 3.02 |
| S2 | Підстанції з необов'язковим диспетчером (OPTIONAL) (KQ8) | 12 | 12 | так | 9 / 4 | 344 / 184 | 17.06 / 3.25 |
| S3 | Навантаження за регіонами (GROUP BY) (KQ3) | 6 | 6 | так | 8 / 4 | 320 / 204 | 20.31 / 3.5 |
| S4 | Усі споживачі (у SPARQL — через виведення підкласів) (KQ1) | 41 | 41 | так | 8 / 3 | 279 / 104 | 9.7 / 1.26 |
| S5 | ASK: чи є підстанція без диспетчера? (KQ8) | 1 | 1 | так | 4 / 1 | 137 / 105 | 6.88 / 1.78 |

Усі 5 пар дали **повністю однакові рядки** (після нормалізації IRI до локальних імен). Пояснення відмінностей, які могли б виникнути:
- **S4 залежить від виведення.** У даних немає жодного `?c a :Consumer`: є лише підкласи. Без RDFS-виведення SPARQL повертає **0 рядків** (перевірено), з виведенням — 41. У Cypher базову мітку `:Consumer` «матеріалізовано» під час імпорту, тому виведення не потрібне.
- **Округлення.** SPARQL `ROUND()` і Cypher `round()` без точності округлюють до цілого (93,6 → 94). У запиті Q2 Результату 3 використано `round(x, 1)`, тому там 93,6.
- **Ідентифікатори.** SPARQL повертає IRI `:Dispatcher_3`, Cypher — рядок `Dispatcher_3`. Для порівняння IRI скорочено.
- **Час** виміряно в середовищі підготовки (rdflib — інтерпретатор SPARQL на Python, Kùzu — колонковий рушій на C++), тому він орієнтовний. Fuseki/Neo4j: ____ / ____ мс.

## 2. Таблиця порівняння

| Критерій | SPARQL (RDF, Fuseki) | Cypher (LPG, Neo4j) |
|---|---|---|
| Читабельність | шаблони триплетів `?s :p ?o`; префікси й IRI додають шуму | ASCII-art шаблони `(a)-[:R]->(b)` наочно повторюють схему |
| Довжина | у середньому 299 символів | у середньому 175 символів (≈ на 41 % коротше) |
| Час (5 запитів, медіана) | 6.88–20.31 мс (rdflib) | 1.26–3.5 мс (Kùzu) |
| Шляхи змінної довжини | property paths `:upstreamOf+`, але без довжини шляху й без самого шляху | `[:FEEDS*1..5]`, `length(p)`, `nodes(p)`, `shortestPath` |
| Виведення / семантика | RDFS/OWL-reasoner (підкласи, обернені, транзитивні властивості) | немає; потрібне явне моделювання (мітки при імпорті) |
| Властивості зв'язків | потрібна реифікація / RDF-star | нативно (`r.confidence`, `r.validFrom`) |
| Інтеграція / стандарти | W3C-стандарт, глобальні IRI, вирівнювання з FOAF/PROV-O, SHACL | GQL (ISO/IEC 39075:2024) близький до Cypher; IRI й зовнішніх словників немає |
| Аналітика графа | немає вбудованої | GDS: PageRank, Louvain тощо |
| Обмеження | відкритий світ, SHACL для валідації | закритий світ, UNIQUE/існування/тип (частина — лише Enterprise) |

Висновок: SPARQL кращий там, де потрібні семантична сумісність, виведення та зв'язок зі зовнішніми словниками. Cypher зручніший для навігації шляхами, аналізу впливу й графової аналітики. Для Domain Knowledge Hub доцільна гібридна схема: RDF як «джерело істини», LPG як аналітична проєкція.

## 3. Text-to-Cypher

Реалізація: `tests/t2c_prompt_v1.md` (системна підказка зі схемою), `tests/t2c_questions.json` (15 питань),
`tests/t2c_gold.json` (еталонні запити й ключові колонки), `tests/t2c_guard.py` (захисний шар),
`tests/t2c_eval.py` (оцінювання), `tests/t2c.jsonl` (по рядку на кожне питання кожного прогону).

**Захисні заходи (C3):**
1. *Схема в підказці* — повний перелік міток, типів зв'язків (з напрямами) і властивостей зі значеннями-словниками.
2. *Перевірка схеми* (`t2c_guard.check`): будь-яка мітка, тип зв'язку чи властивість поза схемою → запит відхиляється до виконання. Це критично, бо Neo4j на невідому властивість не видає помилки, а «тихо» повертає `null`.
3. *Заборона запису*: статичний фільтр (CREATE, MERGE, SET, DELETE, REMOVE, DROP, FOREACH, LOAD CSV, CALL proc.) + виконання від імені користувача `t2c_reader` з вбудованою роллю `reader` (`import/07_t2c_reader.cypher`) у сесії `READ_ACCESS` з тайм-аутом 5 с; попередньо `EXPLAIN`.
4. *LIMIT*: якщо немає — додається `LIMIT 100`; якщо більше — зменшується до 100.

**Метрики (C4).** Прогони: R1 — основна модель (агент Claude Opus) із підказкою v1; R2 — менша модель (Claude Haiku) з тією самою підказкою; R3 — абляція: підказка v0 без формальної схеми. Перші 10 питань R1 не дали жодної помилки, тому набір розширено 5 складнішими питаннями (заперечення, частки, дати, транзитивна агрегація, top-1).

| Прогін | Коректних (автоматично) | Після ручного розгляду | Заблоковано guard | Генерація, с/запит | Виконання, мс (медіана) |
|---|---|---|---|---|---|
| R1: v1 (схема) · Opus-агент | 15/15 (100%) | 15/15 (100%) | 0 | 1.81 | 6.9 |
| R2: v1 (схема) · Haiku-агент | 14/15 (93%) | 15/15 (100%) | 0 | 1.61 | 10.7 |
| R3: v0 (без схеми) · Opus-агент | 5/15 (33%) | 6/15 (40%) | 9 | 1.19 | 34.7 |

**Аналіз трьох помилок** (усі з прогону R3, без схеми):
1. **Вигадані назви властивостей (T02, T08, T14).** Модель вгадала snake_case-конвенцію: `s.current_load`, `s.capacity`, `x.contract_limit` замість `currentLoad`, `nominalCapacity`, `contractLimit`. У Neo4j такий запит **не впав би**: T14 через `coalesce(x.contract_limit, 0)` повернув би суму 0 для всіх диспетчерів — правдоподібну, але хибну відповідь. Захист: перевірка властивостей за схемою (guard відхилив усі три).
2. **Вигадані мітки й типи зв'язків (T04, T05, T07, T10, T11, T13).** Мітки `:Model`, `:Weather`, зв'язки `GENERATES`, `USES`, `FOR`, `AFFECTS`, `RECORDS`. Neo4j повертає на них порожній результат лише з попередженням, і користувач вирішив би, що даних немає. Захист: схема в підказці (у R1/R2 таких помилок 0) і перевірка міток/типів у guard.
3. **Семантична розбіжність при правильній структурі (T12).** Запит проходить усі перевірки й виконується, але повертає частку у відсотках (×100) замість долі, а статус перелічує «на здогад» (`IN ['faulty','broken','несправний']`). Автоматичне порівняння позначило його як хибний; при ручному розгляді він прийнятний. Висновок: потрібні словник значень у підказці (у v1 він є) й еталонні тести з допуском на одиниці виміру.

Додатково (загроза валідності): у R2 автоматична перевірка в Kùzu позначила T14 як хибний через дефект рушія (`list_transform` над списком вузлів). Окремим запитом перевірено, що множини споживачів збігаються з еталоном, тож відповідь моделі правильна. Остаточну метрику слід підтвердити запуском `tests/t2c_eval.py --engine neo4j`.

## 4. Тексти запитів

### S1. Перевантажені підстанції (≥ 85 %) і диспетчер

**SPARQL (ЛР8, запит 1):**
```sparql
PREFIX :     <http://www.semanticweb.org/energy-forecasting#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?name ?load ?capacity (ROUND(100 * ?load / ?capacity) AS ?percent) ?dispatcher
WHERE {
  ?s a :Substation ;
     skos:prefLabel ?name ;
     :currentLoad ?load ;
     :nominalCapacity ?capacity ;
     :managedByDispatcher ?dispatcher .
  FILTER (?load / ?capacity >= 0.85)
}
ORDER BY DESC(?percent)
```
**Cypher:**
```cypher
MATCH (d:Dispatcher)-[:MANAGES]->(s:Substation)
WHERE s.currentLoad / s.nominalCapacity >= 0.85
RETURN s.name AS name, s.currentLoad AS load, s.nominalCapacity AS capacity,
       round(100.0 * s.currentLoad / s.nominalCapacity) AS percent, d.id AS dispatcher
ORDER BY percent DESC
```

### S2. Підстанції з необов'язковим диспетчером (OPTIONAL)

**SPARQL (ЛР8, запит 2):**
```sparql
PREFIX :     <http://www.semanticweb.org/energy-forecasting#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?name ?region ?dispatcher ?shift
WHERE {
  ?s a :Substation ;
     skos:prefLabel ?name ;
     :region ?region .
  OPTIONAL { ?s :managedByDispatcher ?dispatcher .
             ?dispatcher :shift ?shift . }
}
ORDER BY ?name
```
**Cypher:**
```cypher
MATCH (s:Substation)-[:LOCATED_IN]->(r:Region)
OPTIONAL MATCH (d:Dispatcher)-[:MANAGES]->(s)
RETURN s.name AS name, r.name AS region, d.id AS dispatcher, d.shift AS shift
ORDER BY name
```

### S3. Навантаження за регіонами (GROUP BY)

**SPARQL (ЛР8, запит 3):**
```sparql
PREFIX : <http://www.semanticweb.org/energy-forecasting#>
SELECT ?region (COUNT(?s) AS ?substations)
       (SUM(?capacity) AS ?totalCapacity) (SUM(?load) AS ?totalLoad)
WHERE {
  ?s a :Substation ; :region ?region ;
     :nominalCapacity ?capacity ; :currentLoad ?load .
}
GROUP BY ?region
ORDER BY DESC(?totalCapacity)
```
**Cypher:**
```cypher
MATCH (s:Substation)-[:LOCATED_IN]->(r:Region)
RETURN r.name AS region, count(s) AS substations,
       sum(s.nominalCapacity) AS totalCapacity, sum(s.currentLoad) AS totalLoad
ORDER BY totalCapacity DESC
```

### S4. Усі споживачі (у SPARQL — через виведення підкласів)

**SPARQL (ЛР8, запит 4):**
```sparql
PREFIX :     <http://www.semanticweb.org/energy-forecasting#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?name ?category ?limit
WHERE {
  ?c a :Consumer ;
     skos:prefLabel ?name ;
     :consumerCategory ?category ;
     :contractLimit ?limit .
}
ORDER BY ?name
```
**Cypher:**
```cypher
MATCH (c:Consumer)
RETURN c.name AS name, c.category AS category, c.contractLimit AS limit
ORDER BY name
```

### S5. ASK: чи є підстанція без диспетчера?

**SPARQL (ЛР8, запит 5):**
```sparql
PREFIX : <http://www.semanticweb.org/energy-forecasting#>
ASK {
  ?s a :Substation .
  FILTER NOT EXISTS { ?s :managedByDispatcher ?d }
}
```
**Cypher:**
```cypher
RETURN EXISTS { MATCH (s:Substation) WHERE NOT EXISTS { MATCH (:Dispatcher)-[:MANAGES]->(s) } } AS answer
```
