# Журнал взаємодії з LLM (ЛР14)

| № | Дата | Модель і версія | Параметри | Версія підказки | Що запитано / сирий вихід | Рішення людини |
|---|---|---|---|---|---|---|
| 1 | 2026-11-06 | Claude, claude-opus-5-5 (claude.ai) | temperature/seed недоступні | — | Методичка ЛР14 + репозиторій → план 5 результатів, код Р1–Р2 (setup_data, quality_profile, accuracy_sample, dedup) | Прийнято; запущено локально; профіль baseline збережено |
| 2 | 2026-11-06 | Claude, claude-opus-5-5 | — | — | Аналіз pairs_gold.csv: 5 хибних міток із ref_src = extractor; хибне злиття VAR №1 → LSTM1; правило перевірки кластера (`--no-cluster-check` для v1) | Мітки перевірено й виправлено авторкою; правило прийнято (E02, E04 — rejected) |
| 3 | 2026-11-07 | Claude, claude-opus-5-5 | — | — | Чернетка реєстру суперечностей K1–K8 із цитатами, стратегіями й рішеннями; код Р3–Р5 (conflicts, fix_store, shapes.ttl, checks, gate, CI, run_rag) | Цитати перевірено скриптом (27/27); рішення я затвердила; CI запущено на GitHub |
| 4 | 2026-11-07 | Claude, claude-opus-5-5 | — | — | Порівняння RAG до/після, after_report.md, claims.csv, звіт | Числа взято лише з summary.json/records.jsonl; висновки E11–E13, E16 — rejected |
| 5 | 2026-11-06/07 | qwen2.5:7b (Ollama, локально) | temperature 0, seed 42, format=json | dedup_judge_v1 (`prompts/dedup_judge_v1.md`) | 11 спірних пар test → `llm_log/dedup_judge.jsonl` (сирий вихід, причина, затримка) | Порівняно з міткою людини (human_label, human_decision): 10 accept, 1 reject (P074) |
| 6 | 2026-11-07 | qwen2.5:7b (генератор RAG ЛР11), openai/gpt-oss-120b (суддя ЛР11, Groq) | temperature 0, seed 42; суддя — як у ЛР11 | rag_v1, judge — без змін ЛР11 | 39 тестів на корпусі data_after → `results/rag_after/rag_log.jsonl`, `records.jsonl`, `summary.json` | Метрики прийнято; судді передаються лише не-restricted фрагменти (judge_removed_restricted = 0) |

Restricted-документи (gen03, kb15) оброблялися тільки локально (dedup, gate, qwen); у Claude вони не передавалися,
у файлах якості замасковані («[restricted: …]»), перевірка PY5 у CI це контролює.
