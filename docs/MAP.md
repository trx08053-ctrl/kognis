# Карта проекта

> Генерируется `just map` из кода — не редактировать вручную. `just check map` проверяет
> актуальность. Архитектурные правила — [ARCHITECTURE.md](ARCHITECTURE.md),
> границы — `.importlinter`.

Корневой пакет: `kognis` · компонентов: 3

## Компоненты

| Компонент | Назначение | Зависит от | Файлов | Карточка |
|---|---|---|---|---|
| `kognis.db` | Платформа данных: подключение, метаданные таблиц, транзакции. | — | 1 | [db](modules/db.md) |
| `kognis.users` | Модуль users: регистрация и поиск пользователей. Владеет данными пользователей. | `db` | 4 | [users](modules/users.md) |
| `kognis.web` | Модуль web: HTTP-вход приложения — страницы, JSON API, /health. Бизнес-логики не содержит. | `db`, `users` | 2 | [web](modules/web.md) |

## `kognis.db`

- Код: `src/kognis/db`
- Публичный интерфейс:
  - `database_url` — `src/kognis/db/__init__.py`
  - `make_engine` — `src/kognis/db/__init__.py`
  - `metadata` — `src/kognis/db/__init__.py`
  - `transaction` — `src/kognis/db/__init__.py`
- Тесты: `tests/integration/test_postgres.py`, `tests/users/test_users.py`

## `kognis.users`

- Код: `src/kognis/users`
- Публичный интерфейс:
  - `User` — `src/kognis/users/_domain.py`
  - `UserService` — `src/kognis/users/_app.py`
- Тесты: `tests/integration/test_postgres.py`, `tests/users/test_users.py`

## `kognis.web`

- Код: `src/kognis/web`
- Публичный интерфейс:
  - `create_app` — `src/kognis/web/_app.py`
  - `main` — `src/kognis/web/__init__.py`
- Тесты: `tests/web/test_http.py`

## Точки входа

- `kognis` → `kognis.web:main`
