# СР11. Тестування RAG: сценарії відмов

Курс «Сховища знань та управління знаннями», Domain Knowledge Hub, «Прогнозування енергоспоживання».

20 тестових запитів до RAG-чат-бота з ЛР11 (код у `../lab11`, ця папка використовує його `src/`), прогін, класифікація
результатів (правильно / частково / ні) і причин відмов (пошук / контекст / генерація / політика), план виправлень.

| Файл | Що містить |
|---|---|
| `scripts/build_queries.py` → `eval/sr11_queries.jsonl` | 20 запитів: 5 простих, 4 багатокрокові, 4 без відповіді, 3 суперечливі, 4 шкідливі; докази перевіряються на дослівну присутність |
| `scripts/run_sr11.py` → `results/sr11_records.jsonl`, `results/sr11_review.csv`, `results/rag_log.jsonl` | прогін через RAG (фінальна конфігурація ЛР11), відповіді, джерела, автоматична чернетка класифікації, оцінка судді |
| `scripts/summarize.py` → `docs/sr11_summary.md`, `results/sr11_summary.json`, `docs/sr11_causes.png` | розподіл результатів і причин після ручної перевірки |
| `llm_log/README.md`, `claims/claims.csv` | протокол «LLM-експерт» |

## Запуск (Windows, PowerShell; середовище й змінні — з ЛР11)

```powershell
cd "...\lab9-16\sr11"
..\lab11\.venv\Scripts\Activate.ps1
. ..\lab11\set_env.ps1            # генератор Ollama, суддя Groq, Neo4j (ключ і пароль вводяться, не зберігаються)
$env:PYTHONUTF8 = "1"

python scripts/build_queries.py
python scripts/run_sr11.py         # ≈ 30–45 хв на CPU
# ручна перевірка: results/sr11_review.csv — human_label, human_cause, human_comment для всіх 20 рядків,
#                  human_judge_ok (1/0) щонайменше для 5 рядків з оцінкою судді
python scripts/summarize.py
```

Конфігурація: qwen2.5:7b (temperature 0, seed 42), top_k = 5, вікно 150 слів, режим text+graph, вихідний фільтр leak,
роль analyst (restricted-документи не потрапляють ні в промпт, ні до хмарного судді).
