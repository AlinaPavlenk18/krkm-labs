# ЛР9 · Графова база знань у Neo4j — «Прогнозування енергоспоживання»

## Структура

```
data/source/         вхід: data.ttl, vocabulary.ttl, queries.rq, shapes.ttl з ЛР8
data/triples_final.csv   1206 RDF-триплетів із провенансом (source, confidence, valid_from)
data/nodes_*.csv, rels_*.csv   CSV для LOAD CSV (190 вузлів, 314 зв'язків)
docs/                схема (drawio/png), cq_mapping, cypher_results, gds_report, sparql_vs_cypher, очікувані результати (json)
import/              01–07 *.cypher: обмеження, індекси, імпорт, перевірки, порушення обмеження, read-only користувач
queries/             q00 (ручна перевірка), q01–q10 — запити Cypher
gds/                 проєкція, PageRank/Louvain, PROFILE
tests/               text-to-Cypher: підказка, питання, еталон, guard, оцінювання, t2c.jsonl
llm_log/             журнал LLM, сирі виходи text-to-Cypher
claims/claims.csv    таблиця тверджень
scripts/             генерація даних, імпорт, перевірки (Kùzu, networkx), порівняння SPARQL/Cypher
```

## Версії

Neo4j 5.x (Neo4j Desktop, локальна БД) + плагіни **APOC** і **Graph Data Science**; Python ≥ 3.10;
пакети — `requirements.txt`. Seed генератора даних — 42, Louvain — `concurrency: 1`.

## Запуск з нуля

```bash
pip install -r requirements.txt

python scripts/generate_triples.py        # → data/triples_final.csv
python scripts/triples_to_lpg.py          # → data/nodes_*.csv, data/rels_*.csv

# 2. Neo4j Desktop: створити БД 5.x, додати плагіни APOC і Graph Data Science, запустити.
#    Скопіювати data/nodes_*.csv і data/rels_*.csv у папку Import БД (⋯ → Open folder → Import).
export NEO4J_URI=neo4j://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD='<ваш пароль>'
python scripts/check_connection.py        # версія Neo4j і GDS

python scripts/run_import.py

export NEO4J_T2C_USER=t2c_reader NEO4J_T2C_PASSWORD='<пароль>'
python tests/t2c_eval.py --engine neo4j   
python scripts/compare_sparql_cypher.py --cypher neo4j [--fuseki http://localhost:3030/energy/sparql]
```

Контроль без Neo4j:
`python scripts/verify_kuzu.py`, `python scripts/expected_gds.py`, `python tests/t2c_eval.py --engine kuzu`.

## Дані

25 вузлів — ABox ЛР8 (`source = lab08:data.ttl`). 159 вузлів — **синтетичне** розширення, згенероване
детерміновано (`scripts/generate_triples.py`, seed 42) за обмеженнями словника ЛР8. Це навчальні дані, а не
реальні об'єкти. 6 вузлів `:Region` виведено з рядкових значень `region`. Походження кожного вузла
й зв'язку збережено у властивості `source`.

## Безпека

Паролі й ключі API лише в змінних середовища, у коді й звіті їх немає. Text-to-Cypher виконується від імені
користувача з роллю `reader`, у сесії READ_ACCESS, після статичної перевірки (`tests/t2c_guard.py`).
Персональних даних немає: адреси й споживачі синтетичні.
