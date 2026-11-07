# Журнал взаємодії з LLM (ЛР15)

Рівні верифікації в claims/claims.csv: V1 — звірка з джерелом, V2 — запуск коду/тестів, V3 — red teaming, V4 — траєкторні метрики.

| Модель | Де | Роль | Параметри |
|---|---|---|---|
| Claude (Anthropic), claude-opus-5-5, claude.ai | хмара | консультант і червона команда: архітектура, код, сценарії, атаки, аналіз невдач, чернетки docs і звіту | temperature/seed у claude.ai недоступні |
| qwen2.5:7b (Ollama) | локально | «мозок» агента: план, виклики інструментів, відповідь | temperature 0, seed 42, num_ctx 8192 |

## Записи

| № | Дата | Модель | Підказка / версія | Що запитано | Сирий вихід | Рішення людини |
|---|---|---|---|---|---|---|
| 1 | 07.11.2026 | Claude | — | спроєктувати агента за методичкою ЛР15 (LangGraph + MCP, 3 read-only інструменти, HITL) | код lab15, tests/*.jsonl | прийнято; запуск на стенді |
| 2 | 07.11.2026 | qwen2.5:7b | plan_v1, draft_v1 | 5 демо-запитів | logs/trace_demo.jsonl | — |
| 3 | 07.11.2026 | qwen2.5:7b | v1 | 12 сценаріїв | logs/trace_scen_v1.jsonl | 7 провалів передано на аналіз |
| 4 | 07.11.2026 | qwen2.5:7b | v1, AGENT_DEFENSES 0/1 | 7 атак до/після | logs/trace_attack_after.jsonl; прогін «до» — лише зведення (містить restricted) | — |
| 5 | 07.11.2026 | Claude | — | аналіз 3 невдач v1 і виправлення | prompts/*_v2.md, зміни graph.py, tools.py | прийнято; tool_lock перезаписано |
| 6 | 07.11.2026 | qwen2.5:7b | v2 | сценарії й атаки | logs/trace_scen_v2.jsonl, trace_attack_after_v2.jsonl | — |
| 7 | 07.11.2026 | Claude | — | аналіз v2 (регресія S6, вигадані сутності) | prompts/*_v3.md, зміни graph.py | прийнято |
| 8 | 07.11.2026 | qwen2.5:7b | v3 | сценарії й атаки | logs/trace_scen_v3.jsonl, trace_attack_after_v3.jsonl | v3 — фінальна версія |
| 9 | 07.11.2026 | — (людина) | — | 3 пропозиції propose_fact | kb/proposals.json, kb/audit.jsonl | P-0002 схвалено вручну |
| 10 | 07.11.2026 | Claude | — | docs/agent_eval, agent_security, hitl, claims, звіт | docs/*.md | числа звірено з results/*.json |

Restricted-документи (gen03, kb15), ключі й паролі в хмарну модель не передавались. Трасування прогону «до захисту»,
що містить витеклі адреси, не надсилалося і не комітиться.
