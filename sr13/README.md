# СР13 · Порівняння методів витягу відношень — «Прогнозування енергоспоживання»

Три методи витягу відношень (s, p, o) на однакових 50 реченнях із корпусу ЛР13, P/R/F1, вартість/час, аналіз помилок.

| Метод | Що це | Файл |
|---|---|---|
| 1 · правила/шаблони | spaCy EntityRuler + регулярні вирази, правила ЛР13 `rules_v2` без змін | `src/m1_rules.py`, `src/lr13_rules.py` |
| 2 · spaCy-модель | статистична модель `uk_core_news_sm`: шлях у дереві залежностей між згадками + тригер-лема | `src/m2_spacy.py` |
| 3 · LLM зі схемою | `qwen2.5:7b` в Ollama, JSON-схема з переліком предикатів, evidence, валідація, 1 повтор | `src/m3_llm.py`, `prompts/relations_v1.md` |

## Структура

```
data/sentences.csv            50 речень: документ, офсет, група (стаття/реєстр), чи з dev-документа ЛР13
data/gold.csv                 золота розмітка (s, p, o) — виконує людина за docs/annotation_guide.md
data/gold_assistant_draft.csv незалежна чернетка асистента — лише для контролю розмітки (scripts/agree.py)
src/common.py, src/schema.py  нормалізація трійок до ID графа ЛР9 (однакова для всіх методів)
scripts/evaluate.py           P/R/F1 загалом, за предикатами, групами; вартість; results/errors.csv
scripts/explain.py            LLM пояснює сумнівні відношення → llm_log/explanations.jsonl
results/                      виходи методів (*.jsonl), метадані з часом і токенами, сирі відповіді LLM
docs/comparison.md            таблиця F1/вартість, 10 помилок кожного методу, рекомендація
llm_log/, claims/             протокол «LLM-експерт»
```

## Запуск (PowerShell, папка sr13; поруч має лежати lab13 — звідти беруться тексти документів)

```powershell
pip install -r requirements.txt
python -m spacy download uk_core_news_sm
ollama pull qwen2.5:7b

python scripts/make_sentences.py      # data/sentences.csv (+ порожній data/gold.csv, якщо його ще немає)
# розмітити data/gold.csv вручну, потім:
python scripts/agree.py               # контроль: розбіжності з чернеткою асистента → docs/agreement_auto.md

python -m src.m1_rules                # < 1 с
python -m src.m2_spacy                # кілька секунд
python -m src.m3_llm                  # ≈ 20–40 хв на CPU; після зупинки — python -m src.m3_llm --resume
python scripts/evaluate.py            # results/eval.json, results/errors.csv, docs/results_auto.md
python scripts/explain.py             # ≈ 5–15 хв; пояснення сумнівних відношень
```

Версії: Python 3.14 (перевірено також 3.12), spaCy 3.8.18, uk_core_news_sm 3.8.0, Ollama + qwen2.5:7b
(temperature 0, seed 42). Усі методи локальні — ключів API немає, речення нікуди не передаються.
