# Звіт перевірок якості — defects

Сховище: `data_after\store` · корпус: `data_after\corpus\docs.jsonl` · git f42a073 · 2026-11-07T11:35:23

Перевірок: **26** (JSON Schema: 3, SHACL: 11, SPARQL: 5, pytest: 7); порушень: **21**, з них за винятками (waivers): 7, блокувальних: **14**. Результат gate: **FAIL — зміни заблоковано**.

| ID | Інструмент | Правило | Порушень | Виняток | Статус |
|---|---|---|---|---|---|
| SH-LR8 | SHACL | форми ЛР8 (лічильник, категорія, потужність, регіон, модель прогнозу…) | 1 | 0 | ❌ FAIL |
| SH1 | SHACL | навантаження ≤ номінальна потужність | 1 | 0 | ❌ FAIL |
| SH2 | SHACL | канонічні назви областей | 1 | 0 | ❌ FAIL |
| SH3 | SHACL | інтервал зчитування 15/30/60 | 1 | 0 | ❌ FAIL |
| SH4 | SHACL | статус лічильника з довідника | 1 | 0 | ❌ FAIL |
| SH5 | SHACL | точність моделі 0–100 % | 1 | 0 | ❌ FAIL |
| SH6 | SHACL | одна дата навчання xsd:date | 1 | 0 | ❌ FAIL |
| SH7 | SHACL | тип моделі з довідника | 1 | 0 | ❌ FAIL |
| SH8 | SHACL | одна мітка часу вимірювання | 1 | 0 | ❌ FAIL |
| SH9 | SHACL | споживання ≥ 0 | 1 | 0 | ❌ FAIL |
| SH10 | SHACL | вимірювання — рівно один лічильник | 1 | 0 | ❌ FAIL |
| SP1 | SPARQL | немає циклів у ланцюгу живлення | 0 | 0 | ✅ PASS |
| SP2 | SPARQL | кожна підстанція має диспетчера | 1 | 1 | ⚠️ WAIVED |
| SP3 | SPARQL | дата навчання не раніша за навчальні дані | 6 | 6 | ⚠️ WAIVED |
| SP4 | SPARQL | прогноз має модель і підстанцію | 0 | 0 | ✅ PASS |
| SP5 | SPARQL | немає індивідів у несумісних класах | 0 | 0 | ✅ PASS |
| PY1 | pytest | унікальні id вузлів | 0 | 0 | ✅ PASS |
| PY2 | pytest | посилальна цілісність зв'язків | 2 | 0 | ❌ FAIL |
| PY3 | pytest | provenance зв'язків (source, confidence, validFrom) | 0 | 0 | ✅ PASS |
| PY4 | pytest | немає нерозв'язаних суперечностей значень у корпусі | 1 | 0 | ❌ FAIL |
| PY5 | pytest | restricted-тексти й адреси не у файлах якості | 0 | 0 | ✅ PASS |
| PY6 | pytest | статус моделі відповідає правилу kb08 | 0 | 0 | ✅ PASS |
| PY7 | pytest | реєстр сутностей ER без хибних злиттів | 0 | 0 | ✅ PASS |
| JS1 | JSON Schema | схема документів корпусу | 0 | 0 | ✅ PASS |
| JS2 | JSON Schema | схема реєстру суперечностей | 0 | 0 | ✅ PASS |
| JS3 | JSON Schema | схема реєстру сутностей | 0 | 0 | ✅ PASS |

## Порушення

**SH-LR8** (форми ЛР8 (лічильник, категорія, потужність, регіон, модель прогнозу…)):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH1** (навантаження ≤ номінальна потужність):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH2** (канонічні назви областей):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH3** (інтервал зчитування 15/30/60):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH4** (статус лічильника з довідника):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH5** (точність моделі 0–100 %):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH6** (одна дата навчання xsd:date):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH7** (тип моделі з довідника):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH8** (одна мітка часу вимірювання):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH9** (споживання ≥ 0):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SH10** (вимірювання — рівно один лічильник):
- помилка перевірки: ModuleNotFoundError: No module named 'pyshacl'

**SP2** (кожна підстанція має диспетчера):
- Substation_9: немає відповідального диспетчера

**SP3** (дата навчання не раніша за навчальні дані):
- ForecastModel_LSTM1: trainingDate 2026-01-15 раніша за навчальне вимірювання 2026-09-30
- ForecastModel_LSTM2: trainingDate 2025-06-20 раніша за навчальне вимірювання 2026-01-12
- ForecastModel_VAR1: trainingDate 2025-11-01 раніша за навчальне вимірювання 2026-09-29
- ForecastModel_LSTM3: trainingDate 2026-08-30 раніша за навчальне вимірювання 2026-09-30
- ForecastModel_ARIMA1: trainingDate 2026-02-10 раніша за навчальне вимірювання 2026-09-30
- ForecastModel_GRU1: trainingDate 2026-09-01 раніша за навчальне вимірювання 2026-09-30

**PY2** (посилальна цілісність зв'язків):
- HAS_METER: Consumer_1002 → Meter_AMI00000 — немає вузла
- HAS_METER: Consumer_1002 → Meter_AMI00000 — немає вузла

**PY4** (немає нерозв'язаних суперечностей значень у корпусі):
- Louvain.communities: значення 10.0, 12.0, 14.0 без рішення в реєстрі

