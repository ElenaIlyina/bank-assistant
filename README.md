# bank-assistant

Каркас банковского ассистента (домашка, этап 1): FastAPI + Postgres/pgvector + Temporal, кредитный калькулятор в целых копейках.

## Запуск

```sh
make install          # uv sync
make up               # docker-compose: pgvector + Temporal
cp .env.example .env
make migrate          # идемпотентные миграции + сид 5 тестовых кредитов
make run              # uvicorn на :8000
```

## Проверка (criterias.txt)

```sh
make test             # pytest: эталон 5 505 431 коп., сходимость графика, досрочки
make lint             # ruff check + format
make migrate && make migrate   # второй запуск ничего не применяет
```

- `GET /live` — всегда 200
- `GET /ready` — 503, если БД недоступна
- без `DATABASE_URL`/`TEMPORAL_HOST` приложение не стартует
- `POST /loans/{id}/schedule` — график платежей; опционально тело с `early_repayments` и `mode` (`reduce_term` | `reduce_payment`)

## Деньги

Все суммы — целые копейки (int → bigint → JSON int), ставка — базисные пункты (12% = 1200). Доли копейки округляет единственная функция `round_half_up` в `app/calculator.py`. Эталон: кредит 5 000 000 ₽, 12%, 240 мес → платёж **5 505 431 коп.**
