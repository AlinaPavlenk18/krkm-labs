# СР12 · Проєктування зіркової схеми — «Точність прогнозів добового споживання»

```
docs/star_design.md        1 сторінка: процес, зерно, 5 питань, виміри, ієрархії, міри, SCD
docs/star_schema.png       діаграма (джерело star_schema.dot)
sql/ddl.sql                DDL DuckDB
sql/queries/q1…q5.sql      5 запитів, що відповідають на 5 питань
scripts/build.py           DDL → дані → перевірки → 5 запитів → docs/queries_results.md
scripts/ask_llm_schema.py  LLM (qwen2.5:7b, локально) пропонує схему → llm_log/qwen_schema_raw.md
docs/llm_review.md         3 недоліки схеми LLM і їх виправлення
scripts/check_llm_ddl.py   виконує DDL зі схеми LLM у DuckDB
data/source/               факт добового споживання (агрегат ЛР12), підстанції, моделі (граф ЛР9)
```

## Запуск

```powershell
pip install duckdb pandas tabulate requests
python scripts/ask_llm_schema.py   # потрібна Ollama з qwen2.5:7b
python scripts/build.py
python scripts/check_llm_ddl.py
```

Прогнози синтетичні: прогноз = факт × (1 + ε), ε ~ N(зсув; σ) для кожної версії моделі, seed 42.
