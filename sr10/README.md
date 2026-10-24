# СР10 · Експеримент з embeddings

Domain Knowledge Hub, «Прогнозування енергоспоживання». Павленко А. С., ФЕІ-42.

П'ять моделей embeddings (4 багатомовні + 1 англомовна для контролю) і базова лінія BM25 на 30 запитах
із золотою розміткою з ЛР10. Корпус — 341 структурний фрагмент ЛР10 (`data/corpus.jsonl`). Кожен запит
є в трьох варіантах: український оригінал, англійський переклад і українське перефразування.

## Структура

```
data/corpus.jsonl             341 фрагмент (копія з ЛР10)
eval/lab10_gold.jsonl         золотий набір ЛР10 (докази), з нього взято 30 запитів
eval/variants_llm.jsonl       переклади й перефразування (чернетка LLM)
eval/variants_review.csv      аркуш перевірки варіантів людиною
eval/queries.jsonl            30 запитів + докази + золоті фрагменти (gold_chunks)
src/common.py, src/metrics.py токенізація BM25, метрики recall@k / MRR / nDCG (з ЛР10; правило збігу уточнено)
scripts/build_queries.py      крок 1
scripts/run_experiment.py     кроки 2–3 (індекси FAISS, метрики, затримка, розмір, абляції)
scripts/analyze_disagreements.py  крок 4
scripts/run_all.py            усе підряд
docs/queries.md, docs/sr10_tables.md, docs/disagreements.md
results/sr10_results.json, results/environment.json
llm_log/, claims/             протокол «LLM-експерт»
```

## Запуск (Windows, PowerShell, папка sr10)

Можна використати віртуальне середовище ЛР10 — бібліотеки ті самі.

```powershell
..\lab10\.venv\Scripts\Activate.ps1      # або: py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt
python scripts\build_queries.py          # створить eval\variants_review.csv
# перевірити варіанти в Excel (див. нижче), зберегти, ще раз python scripts\build_queries.py
python scripts\run_all.py                # ≈ 10–20 хв; уперше завантажить e5-base (~1,1 ГБ) і bge-m3 (~2,3 ГБ)
```

Без bge-m3: `python scripts\run_all.py --models e5-small e5-base ml-minilm en-minilm` (так виконано основний прогін).
Перерахувати домени й таблиці зі збережених результатів: `python scripts\run_experiment.py --tables-only`.
e5-small, paraphrase-multilingual-MiniLM і all-MiniLM-L6-v2 вже є в кеші після ЛР10.

## Ручний крок: перевірка перекладів і перефразувань

`eval/variants_review.csv` — 60 рядків (30 запитів × en / uk_para). Для кожного: чи збережено зміст оригіналу?
У `decision` — `accept`, `edit` (тоді виправлений текст у `fixed_text`) або `reject`. Перефразування має
передавати те саме питання іншими словами; переклад — бути коректною англійською.

## Відтворюваність

Індекс — FAISS IndexFlatIP (точний пошук) на нормалізованих векторах; потоки CPU фіксуються (`--threads 4`);
затримка — медіана 3 повторів після прогріву. Заглушка для перевірки коду без моделей: `$env:SR10_STUB="1"`.
