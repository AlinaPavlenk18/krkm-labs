# ЛР10 · Векторне сховище та семантичний пошук

Domain Knowledge Hub, предметна область «Прогнозування енергоспоживання». Павленко А. С., ФЕІ-42.

Корпус із 31 документа (341 фрагмент) → 4 стратегії chunking → FAISS HNSW для 3 моделей embeddings →
гібридний пошук BM25 + dense з RRF (k = 60) і reranker cross-encoder → оцінювання на золотому наборі з 50 запитів.
Усе працює локально, без зовнішніх API.

## Структура

```
data/raw/kb/            15 статей бази знань (markdown з YAML-метаданими)
data/raw/generated/     7 реєстрів, згенерованих з графа ЛР9 (scripts/generate_docs.py)
data/raw/project/       9 проєктних документів ЛР9/СР9 + manifest.json з метаданими
data/source/lab09_graph CSV вузлів і зв'язків ЛР9 (вхід генератора)
data/clean/docs.jsonl   очищені документи з секціями
data/corpus.jsonl       341 фрагмент з метаданими (Результат 1)
src/                    common, clean, chunking, encoders, index (FAISS + upsert/delete), hybrid (BM25, RRF, rerank, фільтри), metrics
scripts/                r1_build_corpus, make_gold, r2_chunking, r3_embeddings, r3_upsert, r4_hybrid, r5_eval, kappa, run_all
eval/                   gold_candidates_llm.jsonl (сирий вихід LLM), gold_review.csv (рішення людини), gold.jsonl,
                        kappa_pool.csv (аркуш двох розмітників), kappa_llm_labels.csv
docs/                   corpus_card.md, chunking_cmp.md, embeddings_cmp.md, hybrid_report.md, search_eval.md
results/                JSON з усіма числами (results/cache — кеш ембедінгів, не комітиться)
llm_log/, claims/       протокол «LLM-експерт»
```

## Запуск з нуля (Windows, PowerShell, папка lab10)

Python 3.11 або 3.12. Інтернет потрібен лише для першого завантаження моделей з Hugging Face (~1,5 ГБ; з bge-m3 ще ~2,2 ГБ).

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\run_all.py              # ≈ 15–25 хв на CPU
python scripts\run_all.py --with-bge   # необов'язково: + reranker BAAI/bge-reranker-v2-m3
```

Окремі кроки: `python scripts\r2_chunking.py`, `python scripts\r3_embeddings.py`, `python scripts\r3_upsert.py`,
`python scripts\r4_hybrid.py`, `python scripts\r5_eval.py`. Продовжити з кроку: `python scripts\run_all.py --from r4`.

Перевірка конвеєра без моделей (заглушка TF-IDF, числа НЕ для звіту): `$env:LAB10_STUB="1"; python scripts\run_all.py`.

## Ручні кроки (обов'язкові за методичкою)

1. **Перевірка золотого набору (V3).** Відкрити `eval/gold_review.csv` в Excel. Для кожного з 50 запитів прочитати запит
   і докази, у колонці `decision` поставити `accept`, `reject` або `edit` (і коротко в `comment`). Для `edit` виправити запит
   або доказ у `eval/gold_candidates_llm.jsonl` і змінити `decision` на `accept`. Потім `python scripts\make_gold.py`
   (скрипт перевіряє, що кожен доказ дослівно є в документі).
2. **Два розмітники, κ.** `eval/kappa_pool.csv`: 12 запитів × 6 фрагментів. Розмітник A (авторка) і розмітник B
   (одногрупник/одногрупниця) незалежно ставлять 1/0 у `label_A` / `label_B`: 1 — фрагмент містить відповідь на запит
   повністю або частково. Не дивитися в `kappa_llm_labels.csv` до завершення. Потім `python scripts\kappa.py score`.
3. **Запуск** `python scripts\run_all.py` і скріншоти виводу кожного кроку.

## Параметри та відтворюваність

- chunking: fixed 120 слів / overlap 30; structural ≤ 180 слів, мін. 25; hierarchical — діти 60 слів, батьки ≤ 400; semantic — перцентиль 20, 40–200 слів;
- FAISS: IndexIDMap2(IndexHNSWFlat), METRIC_INNER_PRODUCT, M = 32, efConstruction = 200, efSearch = 64 (також 16 і 128);
- моделі: intfloat/multilingual-e5-small (префікси `query: ` / `passage: `), sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2,
  sentence-transformers/all-MiniLM-L6-v2 (англомовний контроль); reranker cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 (опц. BAAI/bge-reranker-v2-m3);
- RRF k = 60, кандидатів 30 з кожного списку; reranker топ-30 → топ-5/10;
- seed = 42 (генератор документів, заглушка); версії бібліотек пишуться в results/environment.json.
