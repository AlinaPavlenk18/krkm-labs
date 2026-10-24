# Порівняння моделей embeddings (стратегія hierarchical)

Індекс: FAISS IndexIDMap2(IndexHNSWFlat), METRIC_INNER_PRODUCT на нормалізованих векторах; M = 32, efConstruction = 200, efSearch = 64. Запити: 20 (поле r3), з них 5 англійською.

| Модель | Вим. | max_seq | Обрізано фрагм. | Кодування корпусу, с | HNSW, с | recall@5 | recall@5 uk / en | MRR | Затримка p50 / p95, мс |
|---|---|---|---|---|---|---|---|---|---|
| e5-small (intfloat/multilingual-e5-small) | 384 | 512 | 7 | 24.03 | 0.0707 | 0.550 | 0.6 / 0.4 | 0.730 | 73.36 / 83.26 |
| ml-minilm (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) | 384 | 128 | 157 | 5.17 | 0.0246 | 0.475 | 0.511 / 0.367 | 0.625 | 14.33 / 16.99 |
| en-minilm (sentence-transformers/all-MiniLM-L6-v2) | 384 | 256 | 248 | 5.65 | 0.0192 | 0.062 | 0.083 / 0.0 | 0.083 | 6.68 / 8.77 |

Вплив efSearch (recall HNSW відносно точного перебору в топ-10; час лише пошуку на запит):

| Модель | efSearch = 16 | efSearch = 64 | efSearch = 128 |
|---|---|---|---|
| e5-small | 0.95 (0.029 мс) | 1.0 (0.031 мс) | 1.0 (0.04 мс) |
| ml-minilm | 0.99 (0.015 мс) | 1.0 (0.008 мс) | 1.0 (0.011 мс) |
| en-minilm | 0.93 (0.032 мс) | 1.0 (0.024 мс) | 1.0 (0.045 мс) |
