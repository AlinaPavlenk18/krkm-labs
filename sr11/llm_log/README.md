# Журнал взаємодії з LLM (протокол «LLM-експерт»), СР11

1. **LLM-експерт** — Claude (claude.ai), 26.10.2026, `claude-opus-5-5`; temperature / seed — н/д.
2. **Генератор RAG** — qwen2.5:7b (Ollama), temperature 0, seed 42, промпт `../lab11/prompts/rag_v1.md`; сирі виходи — `results/rag_log.jsonl`, `results/sr11_records.jsonl`.
3. **Суддя** — openai/gpt-oss-120b (Groq), temperature 0, seed 42, рубрика `../lab11/prompts/judge_v1.md`; сирі виходи — поле `judge.raw` у `results/sr11_records.jsonl`. Лише public/internal.

| № | Дата | Модель | Параметри | Підказка | Що запитано | Сирий вихід | Рішення людини |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-26 | claude-opus-5-5 | н/д | P1 | 20 запитів 5 категорій з доказами, ключовими фактами й забороненими рядками | `scripts/build_queries.py` | Прийнято. Докази перевірено скриптом, відсутність відповідей s10–s13 — пошуком у корпусі. |
| 2 | 2026-10-26 | claude-opus-5-5 | н/д | P1 | скрипти прогону, автоматичної класифікації й підсумку | `scripts/run_sr11.py`, `scripts/summarize.py` | Прийнято; автоматична класифікація — лише чернетка, усі 20 оцінок визначено вручну. summarize.py виправлено (Excel записував «1.0» і «-»). |
| 3 | 2026-10-26 | qwen2.5:7b | t = 0, seed 42 | rag_v1 | відповіді на 20 запитів | `results/sr11_records.jsonl` | Ручна класифікація: 14 правильно, 4 частково, 2 ні; причини — генерація 4, пошук 1, політика 1. |
| 4 | 2026-10-26 | gpt-oss-120b | t = 0, seed 42 | judge_v1 | faithfulness 14 відповідей | `results/sr11_records.jsonl` (judge) | Перевірено вручну 7, підтверджено 6; s09 не підтверджено (вигадане поле m.reading). |

