# ЛР13 · Видобування знань із текстів — «Прогнозування енергоспоживання»

Два методи витягу сутностей і відношень (А — правила на spaCy, Б — LLM з JSON-схемою), золотий набір із
розділенням dev/test, оцінювання P/R/F1, граф із provenance у Neo4j і асоціативні правила.

## Структура

```
data/raw/                  24 документи: kb01–kb15 (статті ЛР10), gen01–gen07 (реєстри з графа ЛР9), prj10–prj11 (ЛР12, СР12)
data/docs.jsonl            корпус без YAML-заголовків (офсети рахуються від початку тексту)
data/source/               вузли й зв'язки графа ЛР9 (істина для реєстрів, entity linking)
data/gold.jsonl            золотий набір: 754 твердження (422 сутності, 332 відношення), dev/test
data/kappa_pool.csv        40 пар для двох розмітників; data/kappa_key.csv — ключ (не відкривати до розмітки)
docs/extraction_schema.md  Р1: схема, інструкція, JSON-схема, нормалізація; docs/pilot.md — пілот
docs/gold_card.md          Р2: картка набору
src/schema.py              закритий словник типів, нормалізація canonical()
src/extract_rules.py       Р3: метод А (spaCy EntityRuler + шаблони)
src/extract_llm.py         Р3: метод Б (Ollama qwen2.5:7b, JSON-схема, валідація, повтори)
prompts/extract_v*.md      підказки методу Б
src/evaluate.py, scripts/compare.py   Р4: P/R/F1, гібрид, файл помилок
scripts/build_graph.py     Р5: гібрид → entity linking → data/graph_load.cypher, docs/entity_linking.md
scripts/load_neo4j.py      Р5: завантаження в Neo4j + запити-докази
scripts/patterns.py        Р5: асоціативні правила (support, confidence, lift, перестановочний тест, bootstrap)
results/                   виходи методів (JSONL з provenance), метрики, сирі відповіді LLM
llm_log/, claims/          протокол «LLM-експерт»
```

## Версії

Python 3.14 (перевірено також 3.13), spaCy ≥ 3.8.9 (`spacy.blank("uk")`, модель завантажувати не треба),
Ollama з `qwen2.5:7b`, Neo4j 5 (база ЛР9). Seed: 42 (LLM, перестановки, bootstrap, пул κ).

## Запуск з нуля (PowerShell, папка lab13)

```powershell
pip install -r requirements.txt
python scripts/prepare_docs.py                 # data/docs.jsonl
python scripts/build_gold.py                   # data/gold.jsonl
python scripts/kappa.py make                   # пул для двох розмітників (уже є в репозиторії)

python -m src.extract_rules --split dev        # метод А, налаштування
python -m src.extract_llm --split dev --prompt extract_v1     # метод Б, v1 (результати — results/v1/)
python scripts/replay_validator.py results/v1/llm_dev_calls.jsonl results/v1/llm_dev_replay_validator_v2.jsonl
python -m src.extract_llm --split dev --prompt extract_v2     # v2 на dev (підтвердження налаштування)
python scripts/compare.py --split dev

python -m src.extract_rules --split test       # фінальний запуск (один раз)
python -m src.extract_llm --split test --prompt extract_v2    # ≈ 4,4 год на CPU (у нас 15 846 с); перервано — додайте --resume
python scripts/compare.py --split test

python scripts/build_graph.py                  # data/graph_load.cypher
. .\set_env.ps1                                # NEO4J_PASSWORD (файл не в git)
python scripts/load_neo4j.py                   # Neo4j + запити-докази → results/graph_proof.json
python scripts/patterns.py                     # results/patterns.json, docs/patterns_auto.md
python scripts/kappa.py score                  # після розмітки двома людьми → results/kappa.json
```

## Безпека

Restricted-документи (gen03 — реєстр споживачів, kb15 — журнал інцидентів) обробляються лише локально (spaCy,
Ollama, локальний Neo4j). Адреси не є сутностями схеми і в граф не потрапляють. Пароль Neo4j — лише у змінній
середовища.
