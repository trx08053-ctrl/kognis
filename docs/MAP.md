# Карта проекта

> Генерируется `just map` из кода — не редактировать вручную. `just check map` проверяет
> актуальность. Архитектурные правила — [ARCHITECTURE.md](ARCHITECTURE.md),
> границы — `.importlinter`.

Корневой пакет: `kognis` · компонентов: 9

## Компоненты

| Компонент | Назначение | Зависит от | Файлов | Карточка |
|---|---|---|---|---|
| `kognis.access` | Модуль access: TODO ответственность (одно предложение). | — | 4 | [access](modules/access.md) |
| `kognis.ai` | Модуль ai: TODO ответственность (одно предложение). | — | 4 | [ai](modules/ai.md) |
| `kognis.analysis` | Модуль analysis: TODO ответственность (одно предложение). | — | 4 | [analysis](modules/analysis.md) |
| `kognis.db` | Платформа данных: подключение, метаданные таблиц, транзакции. | — | 1 | [db](modules/db.md) |
| `kognis.diary` | Модуль diary: записи дневника и итоги дня; владеет `entries` и `day_reviews`. | `db` | 4 | [diary](modules/diary.md) |
| `kognis.gameplay` | Модуль gameplay: TODO ответственность (одно предложение). | — | 4 | [gameplay](modules/gameplay.md) |
| `kognis.safety` | Модуль safety: TODO ответственность (одно предложение). | — | 4 | [safety](modules/safety.md) |
| `kognis.users` | Модуль users: регистрация, вход, сессии. Владеет данными пользователей и сессий. | `db` | 4 | [users](modules/users.md) |
| `kognis.web` | Модуль web: HTTP-вход приложения — страницы, JSON API, /health. Бизнес-логики не содержит. | `db`, `diary`, `users` | 2 | [web](modules/web.md) |

## `kognis.access`

- Код: `src/kognis/access`
- Публичный интерфейс: —
- Тесты: **нет**

## `kognis.ai`

- Код: `src/kognis/ai`
- Публичный интерфейс: —
- Тесты: **нет**

## `kognis.analysis`

- Код: `src/kognis/analysis`
- Публичный интерфейс: —
- Тесты: **нет**

## `kognis.db`

- Код: `src/kognis/db`
- Публичный интерфейс:
  - `database_url` — `src/kognis/db/__init__.py`
  - `make_engine` — `src/kognis/db/__init__.py`
  - `metadata` — `src/kognis/db/__init__.py`
  - `transaction` — `src/kognis/db/__init__.py`
- Тесты: `tests/diary/test_diary.py`, `tests/integration/test_postgres.py`, `tests/users/test_users.py`

## `kognis.diary`

- Код: `src/kognis/diary`
- Публичный интерфейс:
  - `DayReview` — `src/kognis/diary/_domain.py`
  - `DiaryService` — `src/kognis/diary/_app.py`
  - `Entry` — `src/kognis/diary/_domain.py`
- Тесты: `tests/diary/test_diary.py`, `tests/integration/test_postgres.py`, `tests/web/test_day_reviews.py`

## `kognis.gameplay`

- Код: `src/kognis/gameplay`
- Публичный интерфейс: —
- Тесты: **нет**

## `kognis.safety`

- Код: `src/kognis/safety`
- Публичный интерфейс: —
- Тесты: **нет**

## `kognis.users`

- Код: `src/kognis/users`
- Публичный интерфейс:
  - `SESSION_LIFETIME` — `src/kognis/users/_app.py`
  - `EmailTakenError` — `src/kognis/users/_domain.py`
  - `InvalidCredentialsError` — `src/kognis/users/_domain.py`
  - `User` — `src/kognis/users/_domain.py`
  - `UserService` — `src/kognis/users/_app.py`
- Тесты: `tests/integration/test_postgres.py`, `tests/users/test_users.py`

## `kognis.web`

- Код: `src/kognis/web`
- Публичный интерфейс:
  - `create_app` — `src/kognis/web/_app.py`
  - `main` — `src/kognis/web/__init__.py`
- Тесты: `tests/web/test_day_reviews.py`, `tests/web/test_http.py`

## Точки входа

- `kognis` → `kognis.web:main`
