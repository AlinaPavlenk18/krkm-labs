# Журнал взаємодії з LLM (протокол «LLM-експерт»), ЛР16

1. **LLM-експерт** — Claude (claude.ai), модель `claude-opus-5-5`; temperature і seed недоступні — «н/д».
2. **Компонент системи** — `qwen2.5:7b` в Ollama (локально, CPU), temperature 0, seed 42: перефразування пояснень
   (промпти `prompts/explain_v1.md`, `explain_v2.md`) і агент ЛР15 у демонстраторі.

| № | Дата | Модель | Параметри | Підказка | Що запитано | Сирий вихід | Рішення людини |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-07 | claude-opus-5-5 | н/д | методичка ЛР16 + Hub ЛР8–15 | дизайн рекомендацій, синтетичні дані, оцінка, пояснення, API/UI, Docker | `reco/*`, `api/*`, `ui/*`, `docker-compose.yml`, docs | Прийнято; дані позначено як синтетичні. |
| 2 | 2026-11-07 | qwen2.5:7b | t = 0, seed 42 | explain_v1 | 50 пояснень (10 користувачів × 5) | `results/explanations.jsonl` | Ручна перевірка: 13/50 коректні (`results/explain_review_v1.csv`); v1 відхилено. |
| 3 | 2026-11-07 | claude-opus-5-5 | н/д | — | аналіз помилок пояснень, режим міток v2, виправлення шаблону | `reco/explain.py`, `prompts/explain_v2.md` | Прийнято. |
| 4 | 2026-11-07 | qwen2.5:7b | t = 0, seed 42 | explain_v2 | 50 пояснень | `results/explanations_v2.jsonl` | 20 прийнято автоперевіркою, 30 — шаблон; ручна перевірка — `results/explain_review_v2.csv`. |
| 5 | 2026-11-07 | claude-opus-5-5 | н/д | — | вибір конфігурації, docs, whitepaper, таблиця тверджень (дати AI Act перевірено вебпошуком у СР15) | `docs/*.md`, `docs/whitepaper.pdf`, `claims/claims.csv` | Прийнято; числа звірено з `results/*.json`. |
