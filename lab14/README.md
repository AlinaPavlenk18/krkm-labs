# ЛР14. Якість, очищення та оцінювання сховища знань

Курс «Сховища знань та управління знаннями», Domain Knowledge Hub, область «Прогнозування енергоспоживання».

Сховище = граф Neo4j ЛР9 (CSV-знімок) + RDF-трійки ЛР9 з provenance + онтологія й SHACL ЛР8 + корпус RAG ЛР11;
згадки сутностей — із витягу ЛР13. Знімок baseline робить `scripts/setup_data.py` (контрольні суми — `data/MANIFEST.json`).

## Структура

```
data/                         знімок сховища (baseline), див. scripts/setup_data.py
quality/common.py             завантаження сховища, RDF, нормалізація, маскування restricted, e5-small
quality/facts.py              числові факти корпусу → узгодженість, суперечності значень
quality/quality_profile.py    Р1/Р5: 10 метрик за 8 вимірами, пороги, дашборд → metrics.json, profile_<tag>.md
quality/accuracy_sample.py    Р1: експертна вибірка 30 тверджень → accuracy_sample.csv
quality/dedup.py              Р2: entity resolution (blocking, рядки + ідентифікатор + тип + ембедінги, поріг на dev,
                              LLM-суддя, злиття з provenance, unmerge) → pairs_gold.csv, out/entities_resolved.json
quality/conflicts.py          Р3: виявлення (facts, SPARQL-виведення + OWL-RL, часові правила), перевірка цитат, conflicts.md
quality/conflicts_registry.json  Р3: суперечності, альтернативи з provenance, стратегії, рішення
quality/fix_store.py          Р3/Р5: нова версія сховища data_after/ (примітки, kb16, alternatives.ttl, статуси, злиття секцій)
quality/shapes.ttl            Р4: SHACL-форми SH1–SH10
quality/checks.py, gate.py    Р4: 26 перевірок (SHACL, SPARQL, pytest, JSON Schema), звіт і тренд → quality/reports/
quality/tests/, schemas/, waivers.json   Р4: pytest, JSON-схеми, відомі порушення з власником і терміном
../.github/workflows/quality.yml         Р4: CI (GitHub Actions) — gate блокує коміт із порушеннями
scripts/inject_defects.py     Р4: 3 навмисні дефекти для демонстрації
scripts/run_rag.py            Р5: тестовий набір RAG ЛР11 на корпусі data_after (код ЛР11 без змін)
prompts/dedup_judge_v1.md     підказка LLM-судді (локальна qwen2.5:7b)
llm_log/, claims/             протокол «LLM-експерт»
```

## Встановлення (PowerShell, папка lab14)

Використовується середовище ЛР11 (там уже є sentence-transformers і модель e5-small у кеші Hugging Face):

```powershell
cd lab14
..\lab11\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Запуск — етап 1 (Р1, Р2)

```powershell
python scripts/setup_data.py                 # знімок baseline
python quality/accuracy_sample.py            # 30 тверджень → заповнити expert_ok (1/0) і expert_comment
python quality/quality_profile.py --ref-date 2026-11-07   # профіль baseline → quality/metrics.json, quality/profile_baseline.md

python quality/dedup.py candidates           # записи, blocking, ознаки
python quality/dedup.py sample               # 120 пар → quality/pairs_gold.csv; заповнити label (1/0)
python quality/dedup.py tune                 # поріг на dev
python quality/dedup.py eval                 # P/R/F1 на test + абляція
ollama serve                                 # (якщо не запущено) локальна модель для судді
python quality/dedup.py judge                # LLM-суддя на спірних парах test
python quality/dedup.py eval                 # повторно — додасться рядок «з LLM-суддею»
python quality/dedup.py merge                # злиття → quality/out/entities_resolved.json, merge_log.jsonl
python quality/dedup.py unmerge --record <rid> --reason "<чому>"
```

Seed 42 (вибірки, LLM), temperature 0. Restricted-документи (gen03, kb15) обробляються лише локально; у CSV/MD
замість їхніх цитат — «[restricted: …]», адреси замасковано.

## Запуск — етап 2 (Р3, Р4, Р5)

```powershell
python quality/conflicts.py detect --ref-date 2026-11-07   # автоматичне виявлення
python quality/conflicts.py check                          # усі цитати реєстру є в джерелах
python quality/conflicts.py report                         # quality/conflicts.md (журнал рішень)
python quality/fix_store.py --ref-date 2026-11-07          # data_after/ — нова версія сховища

python quality/gate.py --version baseline --record --name baseline --ref-date 2026-11-07   # очікувано FAIL
python quality/gate.py --record --name after --ref-date 2026-11-07                        # очікувано PASS
$env:QUALITY_REF_DATE = "2026-11-07"; pytest -q quality/tests
python scripts/inject_defects.py; python quality/gate.py --record --name defects --ref-date 2026-11-07  # FAIL: 3 дефекти
python quality/fix_store.py --ref-date 2026-11-07; python quality/gate.py --record --name fixed --ref-date 2026-11-07

python quality/quality_profile.py --tag after --store data_after/store --corpus data_after/corpus/docs.jsonl --ref-date 2026-11-07
. .\set_env.ps1                                              # ключ судді (як у ЛР11), файл не в git
python scripts/run_rag.py --version after                   # ≈ 2–3 год; результати results/rag_after/
```
