# ЛР16. Рекомендаційна система та фінальний демонстратор

Рекомендації фрагментів знань Domain Knowledge Hub «Прогнозування енергоспоживання»: графовий підхід (Personalized
PageRank на графі знань), embeddings (e5-small, kNN), популярнісний baseline і гібрид (зважений RRF); фільтри прав
(kb10), якості (ЛР14 verified) і свіжості; пояснення зі шляхів графа з автоперевіркою; холодний старт; демонстратор
(FastAPI + Streamlit + агент ЛР15) у Docker Compose. Проєкт: docs/reco_design.md.

## Передумови
- Docker Desktop (Compose v2), ≈ 6 ГБ диска для образу; Ollama на хості з `qwen2.5:7b` (для агента й LLM-пояснень)
  — або профіль `ollama` у compose.
- Для локального запуску без Docker: Python 3.12–3.14, `pip install -r requirements.txt` (torch — CPU).
- Каталоги репозиторію `lab11`, `lab12`, `lab14`, `lab15` поруч із `lab16`.

## Запуск однією командою
```powershell
cd lab16
docker compose up --build          # UI: http://localhost:8501, API: http://localhost:8000/docs
```
| Змінна | За замовчуванням | Призначення |
|---|---|---|
| GEN_BASE_URL | http://host.docker.internal:11434 | Ollama для агента й пояснень |
| GEN_MODEL | qwen2.5:7b | модель |
| AGENT_DEFENSES / AGENT_PROMPT | 1 / v3 | захисти й промпти агента ЛР15 |
| HF_HUB_OFFLINE | 1 | моделі пошуку вже в образі |
Ключів API немає; змінні — у `.env` поруч із compose (не в git).

## Дані й відтворення (seed 42)
```powershell
python -m reco.synth --seed 42                 # data/users.csv, data/interactions.csv (опис — docs/reco_design.md)
python -m reco.eval                            # 4 конфігурації × 5 метрик, бутстреп, 5 повторів → results/eval.json, reco_metrics.png
python -m reco.explain --users 10 --k 5        # пояснення + перевірка → results/explanations.jsonl, explain_summary.json
python -m reco.cli filters --user u013         # демо фільтрів
python -m reco.cli cold-user --role dispatcher --group Dispatcher_2
python -m reco.cli cold-doc --doc kb16 --user u013
python -m pytest tests/test_reco.py -q
```
Часове розбиття: train < 27.10.2026, test 27.10–06.11; ваги гібриду — на валідації (train < 20.10, перевірка 20–26.10).
