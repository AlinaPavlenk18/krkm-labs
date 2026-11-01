# ЛР12 · OLAP-куб на основі таксономії — «Прогнозування енергоспоживання»

Зіркова схема погодинного споживання електроенергії в DuckDB: вимір-таксономія класів споживачів (IRI онтології),
OLAP-запити, семантичний шар метрик, text-to-SQL із захистами та аналітична панель.

## Структура

```
docs/star_design.md, docs/star_schema.png   Р1: зерно, питання, виміри, міри, SCD, діаграма
sql/ddl.sql                                  Р1: DDL DuckDB
etl/generate.py, etl/load.py                 Р2: генератор (seed 42) і ELT з перевірками якості
data/*.parquet, data/VERSION.json            Р2: таблиці сховища, версія набору, звіт якості
docs/quality_report.md
sql/olap/q01…q10.sql, docs/olap_results.md   Р3: 10 OLAP-запитів з питаннями й інтерпретаціями
scripts/run_olap.py, scripts/verify_pandas.py
semantic/metrics.yml, semantic/semantic.py   Р4: 7 метрик і генерація SQL за метрикою
scripts/check_semantic.py, docs/semantic_layer.md
t2sql/t2sql.py, prompts/t2sql_v1.md          Р5: text-to-SQL (AST, read-only, LIMIT, тайм-аут)
tests/test_guard.py, tests/t2sql_questions.jsonl, tests/t2sql.jsonl, scripts/run_t2sql.py
dashboard/build_dashboard.py, dashboard/index.html, dashboard/*.png   Р5: панель
docs/t2sql_errors.md, docs/risks.md          Р5: аналіз помилок text-to-SQL, ризики
data/source/*.csv                            вхід: вузли й зв'язки графа ЛР9
llm_log/README.md, claims/claims.csv         протокол «LLM-експерт»
```

## Версії

Python 3.14 (перевірено також 3.13), DuckDB ≥ 1.4, Ollama з моделлю `qwen2.5:7b` (лише для text-to-SQL).
Seed генератора — 42; text-to-SQL — temperature 0, seed 42.

## Запуск з нуля (Windows PowerShell)

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt

python etl/generate.py            # data/raw/*.csv
python etl/load.py                # data/warehouse.duckdb, data/*.parquet, перевірки якості
python scripts/run_olap.py        # docs/olap_results.md
python scripts/verify_pandas.py   # незалежна перевірка 2 результатів
python scripts/check_semantic.py  # docs/semantic_layer.md
python tests/test_guard.py        # захисти text-to-SQL без LLM
python scripts/run_t2sql.py --engine gold   # самоперевірка конвеєра еталонними SQL

ollama pull qwen2.5:7b
python scripts/run_t2sql.py       # 16 питань → tests/t2sql.jsonl, results/t2sql_summary.json
python scripts/run_t2sql.py --rescore   # переоцінити збережені відповіді без виклику LLM
python dashboard/build_dashboard.py
```

Генерувати SQL за метрикою: `python semantic/semantic.py peak_load substation`.

## Дані

Сутності (41 споживач, 43 лічильники, 12 підстанцій, 6 областей) — з графа ЛР9. Погодинні показання за січень 2026
**синтетичні** (`etl/generate.py`, формули профілів у docstring). Це навчальні дані, а не реальні вимірювання.
Адреси споживачів у сховище не завантажуються.

## Безпека

Text-to-SQL працює з локальною моделлю; виконання — у read-only з'єднанні без доступу до файлів, після AST-перевірки.
Ключів API ця робота не потребує.
