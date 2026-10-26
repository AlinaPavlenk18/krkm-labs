# ЛР11. Чат-бот на основі гібридного сховища (RAG + граф)

Курс «Сховища знань та управління знаннями», Domain Knowledge Hub, область «Прогнозування енергоспоживання».

Вхід: корпус і гібридний пошук ЛР10 (BM25 + multilingual-e5-small, RRF, reranker mMiniLM; hierarchical chunking),
золотий набір ЛР10 (`data/lab10_gold.jsonl`), граф знань ЛР9 (Neo4j; CSV-копія в `data/graph`).

## Архітектура

```
питання ─► гібридний пошук ЛР10 з pre-filter за роллю ─► reranker ─► топ-k фрагментів (вікно 150 слів)
        └► [text+graph] entity linking ─► підграф Neo4j (1–2 кроки, ≤ 25 фактів) ─► факти [g1]…[gN]
   ─► промпт prompts/rag_v1.md ─► генератор Ollama (qwen2.5:7b, temperature 0, seed 42)
   ─► перевірка цитат (усі [id] ∈ контекст) ─► журнал logs/rag_log.jsonl ─► відповідь / REST API
оцінювання: eval/rag_eval.jsonl (39 тестів) ─► автометрики + суддя (інша модель, хмарний API, prompts/judge_v1.md)
```

| Результат | Артефакти |
|---|---|
| 1. RAG-конвеєр із цитуванням | `src/rag.py`, `src/llm.py`, `prompts/rag_v1.md`, `scripts/demo.py`, `logs/rag_log.jsonl` |
| 2. Підграф у контексті | `src/graph_context.py`, `scripts/graph_compare.py`, `eval/graph_questions.jsonl`, `docs/graph_vs_text.md` |
| 3. REST API | `api/main.py`, `tests/test_api.py`, `scripts/api_demo.py`, `docs/api.md`, `docs/openapi.json` |
| 4. Тестовий набір і метрики | `eval/rag_eval.jsonl`, `scripts/build_eval.py`, `src/judge.py`, `prompts/judge_v1.md`, `scripts/run_eval.py`, `scripts/judge_agreement.py`, `docs/rag_eval.md` |
| 5. Оптимізація «до/після» | `scripts/compare_runs.py`, `docs/rag_optimization.md` |
| Протокол «LLM-експерт» | `llm_log/README.md`, `claims/claims.csv` |

## Встановлення (Windows, PowerShell; Python 3.11–3.12)

```powershell
cd lab11
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Моделі пошуку (`intfloat/multilingual-e5-small`, `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) завантажуються з
Hugging Face під час першого запуску (як у ЛР10).

### Генератор — локальна модель Ollama

1. Встановити Ollama: https://ollama.com/download ; перевірити: `ollama --version`.
2. `ollama pull qwen2.5:7b` (≈ 4,7 ГБ). Якщо комп'ютер без відеокарти й одна відповідь триває > 1 хв — `qwen2.5:3b`.
3. Змінні (типові значення вже такі, задавати лише для іншої моделі):

```powershell
$env:GEN_PROVIDER = "ollama"; $env:GEN_BASE_URL = "http://localhost:11434"; $env:GEN_MODEL = "qwen2.5:7b"
```

Локальна модель безкоштовна → `cost_usd = 0`. Щоб оцінити вартість для хмарного тарифу, задайте ціни за 1 млн
токенів: `$env:PRICE_IN_PER_M = "..."`; `$env:PRICE_OUT_PER_M = "..."` (взяти з офіційної сторінки цін обраного провайдера).

### Суддя — інша модель через OpenAI-сумісний хмарний API (приклад: Groq)

Ключ створити на https://console.groq.com/keys ; актуальні ID моделей — https://console.groq.com/docs/models.
Ключ лише у змінній середовища, у код і звіт не потрапляє.

```powershell
$env:JUDGE_BASE_URL = "https://api.groq.com/openai/v1"
$env:JUDGE_MODEL    = "openai/gpt-oss-120b"
$env:JUDGE_EXTRA    = '{"reasoning_effort": "low"}'
$env:JUDGE_API_KEY  = "<ваш ключ>"
# необов'язково: ціни судді за 1 млн токенів зі сторінки моделі (для gpt-oss-120b на сторінці Groq: вхід 0.15, вихід 0.60 $)
$env:JUDGE_PRICE_IN_PER_M = "0.15"; $env:JUDGE_PRICE_OUT_PER_M = "0.60"
```

`JUDGE_EXTRA` — необов'язкові параметри запиту; якщо API відповість 400 через `reasoning_effort`, видаліть змінну
(`Remove-Item Env:JUDGE_EXTRA`). На безкоштовному тарифі суддя може відповідати 429 — клієнт сам чекає й повторює.

Захист даних: оцінювання ведеться від ролі `analyst` (у контекст не потрапляють restricted-документи kb15 і gen03),
а `src/judge.py` додатково вилучає restricted-фрагменти перед відправленням судді.

### Граф — Neo4j із ЛР9

Запустіть базу ЛР9 (Neo4j Desktop / Docker) і задайте:

```powershell
$env:GRAPH_BACKEND = "neo4j"; $env:NEO4J_URI = "neo4j://localhost:7687"; $env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<ваш пароль>"   
```

Якщо Neo4j недоступний, модуль друкує попередження й використовує CSV-копію графа (`GRAPH_BACKEND=csv`).

## Запуск з нуля (seed = 42, temperature = 0)

```powershell
# 0. перевірка коду без моделей і мережі (заглушки)
$env:LAB11_STUB = "1"; $env:GRAPH_BACKEND = "csv"; pytest -q tests; Remove-Item Env:LAB11_STUB

# 1. Результат 1: демо 6 запитів, журнал logs/rag_log.jsonl
python scripts/demo.py
python scripts/demo.py --mode text+graph

# 2. Результат 2: 12 питань про зв'язки, «текст» vs «текст + граф»
python scripts/graph_compare.py          # → results/graph_compare/, docs/graph_vs_text_table.md

# 3. Результат 3: API (окреме вікно PowerShell)
$env:LAB11_API_KEYS = '{"an-123": "analyst", "ext-456": "external", "disp-789": "dispatcher"}'
uvicorn api.main:app --port 8000
#    в іншому вікні:
$env:DEMO_KEY_ANALYST = "an-123"; $env:DEMO_KEY_EXTERNAL = "ext-456"; $env:DEMO_KEY_DISPATCHER = "disp-789"
python scripts/api_demo.py

# 4. Результат 4: тестовий набір і оцінювання
python scripts/build_eval.py             # eval/rag_eval.jsonl (39 тестів, перевірка доказів)
python scripts/run_eval.py --name baseline
#    відкрити results/baseline/judge_review.csv, поставити human_supported = 1/0 щонайменше в 10 рядках
python scripts/judge_agreement.py --name baseline

# 5. Результат 5: один керований фактор — top_k 5 → 3
python scripts/run_eval.py --name topk3 --set top_k=3
python scripts/compare_runs.py --a baseline --b topk3
```

Значення ключів у прикладі (`an-123` …) — лише локальні демонстраційні; для реального сервісу генеруються випадкові.

## Версії

Python 3.12; sentence-transformers 3+, faiss-cpu 1.8+, rank-bm25 0.2.2, FastAPI 0.110+, Pydantic 2, neo4j 5.20+;
Ollama + qwen2.5:7b (генератор), суддя — `JUDGE_MODEL`; точні версії середовища фіксуються в `results/*/summary.json`.
Гілка репозиторію: `lab11`.

## Після першого прогону (аналіз провалів і вимірювання вартості)

```powershell
python scripts/guard_offline.py                       # ефект вихідного фільтра на збережених відповідях → docs/guard_effect_table.md
python scripts/measure_cost.py                        # точні токени (токенізатор Qwen2.5) + контрольований вимір затримки top_k 5 vs 3
python scripts/judge_agreement.py --file results/judge_review_v2.csv   # узгодженість судді з людиною (supported і cited_ok)
```

Вихідний фільтр `output_guard` (src/rag.py) вилучає з відповіді службову мітку й дослівні фрагменти системного
промпту (`GUARD_LEAK=1`, увімкнено); необов'язковий режим `GUARD_UNCITED=1` замінює відповідь без валідних цитат на «не знаю».
