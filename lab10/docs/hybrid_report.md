# Гібридний пошук і reranking (модель e5-small, reranker mmarco, стратегія hierarchical)

RRF: k = 60, кандидатів з кожного списку 30; reranker переранжовує топ-30 після RRF.

| Режим | recall@5 | recall@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| bm25 | 0.624 | 0.657 | 0.642 | 0.580 |
| dense | 0.601 | 0.742 | 0.745 | 0.631 |
| hybrid | 0.638 | 0.742 | 0.775 | 0.652 |
| hybrid_rerank | 0.700 | 0.804 | 0.793 | 0.697 |

Reranker змінив склад топ-5 у 42 з 43 запитів, порядок — у 43.

Приклад (q31: «retraining triggers forecasting model error»): hybrid топ-5 = ['prj03#par005', 'kb03#par002', 'prj03#par010', 'prj03#par006', 'kb03#par003']; після reranker = ['prj03#par005', 'kb08#par001', 'prj03#par010', 'prj02#par001', 'prj04#par004']; ранг першого релевантного None → 2.

## Pre-filter за метаданими

| Запит | Фільтр | Порушень без фільтра | pre-filter: результатів / порушень | post-filter: результатів |
|---|---|---|---|---|
| q35 | роль «зовнішній користувач»: лише public | 3 | 5 / 0 | 5 |
| q39 | роль «аналітик»: public + internal (без restricted) | 0 | 5 / 0 | 5 |
| q14 | лише нормативні документи (regulation, procedure, policy) | 2 | 5 / 0 | 5 |
| q19 | лише документи від 2026-10-15 | 1 | 5 / 0 | 5 |

## Ранг першого релевантного фрагмента: виграші та програші hybrid

| Запит | Тип | bm25 | dense | hybrid | hybrid_rerank |
|---|---|---|---|---|---|
| q25 «Який день у навчальних даних був найморознішим?» | paraphrase/uk | 4 | 2 | 1 | 5 |
| q22 «Як оцінювати прогноз, коли фактичне споживання майже нульове?» | paraphrase/uk | None | 9 | 9 | 1 |
| q31 «retraining triggers forecasting model error» | keyword/en | None | 8 | None | 2 |

Перші три рядки — виграші (з 2), останній — програш (з 6). None = немає в топ-10.
