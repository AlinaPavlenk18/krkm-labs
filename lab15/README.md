# ЛР15. LLM-агент з інструментами (LangGraph + MCP) над сховищем знань

Агент відповідає на питання про мережу «Прогнозування енергоспоживання», викликаючи read-only інструменти
`search_docs` (документи ЛР11/ЛР14), `graph_query` (граф ЛР9, SPARQL-шаблони), `sql_metric` (OLAP ЛР12) і цитуючи
кожен факт. Специфікація — docs/agent_spec.md.

## Середовище
Windows 11, Python 3.14, CPU; Ollama `qwen2.5:7b` (локально; temperature 0, **seed 42**, num_ctx 8192);
віртуальне середовище ЛР11 (`lab11\.venv`) + `pip install -r lab15\requirements.txt`
(langgraph 1.x, mcp 2.x, rdflib, pyshacl, jsonschema, duckdb, pyyaml). Потрібні сусідні каталоги
`lab11` (пошук), `lab12` (data/*.parquet, semantic/), `lab14` (data_after/, quality/shapes.ttl). Neo4j не потрібен.

## Запуск з нуля (з каталогу lab15)
```powershell
..\lab11\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:AGENT_DEFENSES="1"
python -m agent.tools --lock                       # зафіксувати SHA-256 описів інструментів
python -m pytest tests/test_tools.py -q            # read-only і захисти (без LLM)
python -m agent.run ask "Які підстанції зараз перевантажені?"     # трасування → logs/trace_demo.jsonl
python -m agent.run scenarios --tag v1             # 12 сценаріїв → results/scenarios_v1_summary.json
$env:AGENT_PROMPT="v3"; $env:HF_HUB_OFFLINE="1"   # фінальна версія (v2 — проміжна); моделі пошуку з локального кешу
python -m agent.tools --lock
python -m agent.run scenarios --tag v3
python -m agent.run attacks --tag after_v3
$env:AGENT_DEFENSES="0"; python -m agent.run attacks --tag before
$env:AGENT_DEFENSES="1"; python -m agent.run attacks --tag after
python -m mcp_server.client_demo                   # MCP: список інструментів і виклики → logs/mcp_demo.jsonl
python -m agent.propose_fact propose --subject ForecastModel_LSTM2 --predicate status --object "застаріла" --source gen02 --quote "Статус: застаріла, у черзі на перенавчання"
python -m agent.propose_fact approve --id P-0002 --by "Павленко А. С."
python -m agent.propose_fact metrics               # HITL, усі 3 сценарії — docs/hitl.md
```

| Каталог | Зміст |
|---|---|
| agent/ | граф LangGraph, інструменти, політики, LLM-клієнт, трасування, propose_fact |
| mcp_server/ | MCP-сервер energy-kb і демонстраційний клієнт |
| prompts/ | версії промптів (plan, draft) |
| tests/ | agent_scenarios.jsonl, attacks.jsonl, test_tools.py |
| docs/ | agent_spec, agent_eval, agent_security, hitl |
| logs/, results/, kb/ | трасування, зведення прогонів, пропозиції / схвалені факти / аудит |

## Результати (qwen2.5:7b, seed 42)
Сценарії v1 → v2 → v3: частка успішних 0,417 → 0,500 → 0,500 (ручна перевірка 5 → 7 → 8 з 12), docs/agent_eval.md.
Атаки: заблоковано 0,571 до захисту → 1,0 після, docs/agent_security.md. HITL: 3 сценарії, docs/hitl.md.
