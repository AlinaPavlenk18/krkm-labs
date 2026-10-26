# REST API чат-бота Domain Knowledge Hub (ЛР11, Результат 3)

Реалізація: `api/main.py` (FastAPI). Повна специфікація OpenAPI 3: `docs/openapi.json`
(також доступна: `http://127.0.0.1:8000/docs` — Swagger UI, `/openapi.json`).

## Ендпоїнти

| Метод і шлях | Автентифікація | Призначення | Коди відповіді |
|---|---|---|---|
| `GET /health` | ні | стан сервісу: модель, версія промпту, бекенд графа | 200 |
| `POST /ask` | `X-API-Key` | питання → відповідь з цитатами `[id]`, джерела, факти графа, токени, затримка | 200, 401, 422, 429, 503 |
| `GET /sources/{id}` | `X-API-Key` | повний текст фрагмента (`id` з поля `sources`, символ `#` кодується як `%23`) | 200, 401, 403, 404 |

### Тіло `POST /ask` (валідація Pydantic, зайві поля заборонені)

| Поле | Тип | Обмеження | Типово |
|---|---|---|---|
| `question` | рядок | 3–500 символів, не порожній | — |
| `mode` | рядок | `text` або `text+graph` | `text` |
| `top_k` | ціле | 1–10 | 5 |

### Відповідь `POST /ask`

`request_id`, `role`, `mode`, `answer`, `citations`, `invalid_citations` (id, яких не було в контексті),
`abstained` (відповідь «Не знаю…»), `sources` (id, title, section, date, sensitivity), `graph_facts`
(рядки `[gN] вузол —ЗВ'ЯЗОК→ вузол`), `tokens` (prompt / completion / total), `latency_ms` (retrieval / graph / llm / total).

## Автентифікація та ролі

API-ключ у заголовку `X-API-Key`. Ключі не зберігаються в коді й репозиторії: їх задає змінна
`LAB11_API_KEYS` (JSON `{"ключ": "роль"}`) або файл `api/keys.json` (внесено до `.gitignore`).

| Роль | Найвищий доступний рівень | Що бачить |
|---|---|---|
| `external` | public | лише публічні статті |
| `analyst` | internal | public + internal (звіти, моделі, правила) |
| `dispatcher`, `admin` | restricted | усе, зокрема журнал інцидентів kb15 і реєстр споживачів gen03 з адресами |

Права застосовуються двічі: (1) pre-filter у пошуку — фрагменти вищого рівня не потрапляють у промпт LLM;
(2) `GET /sources/{id}` повертає 403 для фрагмента вищого рівня. Адреси споживачів у фактах графа
додаються лише для ролей із доступом до restricted.

## Ліміти та помилки

* Ліміт: `RATE_LIMIT_PER_MIN` запитів `/ask` на один ключ за ковзне вікно 60 с (типово 10).
  Понад ліміт — `429 Too Many Requests` із заголовком `Retry-After` (секунди).
* `401` — немає заголовка або невідомий ключ (`WWW-Authenticate: API-Key`);
  `403` — джерело вищого рівня конфіденційності; `404` — немає такого джерела;
  `422` — невалідне тіло (довжина питання, `mode`, `top_k`, зайві поля);
  `503` — генератор LLM (Ollama) або граф недоступні (`Retry-After: 30`).

## Запуск

```bash
cd lab11
export LAB11_API_KEYS='{"<ключ_аналітика>": "analyst", "<ключ_зовнішній>": "external", "<ключ_диспетчера>": "dispatcher"}'
export RATE_LIMIT_PER_MIN=10
uvicorn api.main:app --port 8000
```

## Приклади curl

(PowerShell: замість `\` переносу рядка — один рядок, або `curl.exe`; ключі підставте свої.)

```bash
# 1. Стан сервісу
curl -s http://127.0.0.1:8000/health

# 2. Питання від аналітика (текстовий режим)
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "X-API-Key: $KEY_ANALYST" -H "Content-Type: application/json" \
  -d '{"question": "Що має зробити диспетчер, коли навантаження підстанції перевищило 95 %?", "top_k": 5}'

# 3. Питання про зв'язки з підграфом
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "X-API-Key: $KEY_ANALYST" -H "Content-Type: application/json" \
  -d '{"question": "Які підстанції напряму живить підстанція №1?", "mode": "text+graph"}'

# 4. Те саме питання про інциденти від двох ролей: external / dispatcher — різні джерела
curl -s -X POST http://127.0.0.1:8000/ask -H "X-API-Key: $KEY_EXTERNAL" -H "Content-Type: application/json" \
  -d '{"question": "Які інциденти зафіксовано в журналі диспетчерської служби в жовтні 2026 року?"}'
curl -s -X POST http://127.0.0.1:8000/ask -H "X-API-Key: $KEY_DISPATCHER" -H "Content-Type: application/json" \
  -d '{"question": "Які інциденти зафіксовано в журналі диспетчерської служби в жовтні 2026 року?"}'

# 5. Повний текст джерела: analyst → 403, dispatcher → 200
curl -s -i http://127.0.0.1:8000/sources/kb15%23par000 -H "X-API-Key: $KEY_ANALYST"
curl -s -i http://127.0.0.1:8000/sources/kb15%23par000 -H "X-API-Key: $KEY_DISPATCHER"

# 6. Помилки: без ключа → 401; top_k = 50 → 422; 11-й запит за хвилину → 429
curl -s -i -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d '{"question": "тест"}'
curl -s -i -X POST http://127.0.0.1:8000/ask -H "X-API-Key: $KEY_ANALYST" -H "Content-Type: application/json" \
  -d '{"question": "Що таке MAPE?", "top_k": 50}'
```

Приклад відповіді 422 (FastAPI):

```json
{"detail": [{"type": "less_than_equal", "loc": ["body", "top_k"], "msg": "Input should be less than or equal to 10", "input": 50, "ctx": {"le": 10}}]}
```

## Перевірка

* Автотести: `LAB11_STUB=1 GRAPH_BACKEND=csv pytest -q tests` — 18 тестів (200, 401, 422 ×6, 429 + Retry-After,
  права ролей у пошуку й `/sources`, 404, 503 при недоступному LLM).
* Демо для двох ролей на запущеному сервері: `python scripts/api_demo.py` (ключі в `DEMO_KEY_ANALYST`,
  `DEMO_KEY_EXTERNAL`, `DEMO_KEY_DISPATCHER`).
