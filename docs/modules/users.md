# Модуль `users`

> Публичные символы и фактические зависимости — `just context users`.

- **Назначение:** регистрация, вход/выход, хэш пароля и сессии. Не отвечает за записи дневника и права по тарифам.
- **Публичный API:** `src/kognis/users/__init__.py` — `User`, `UserService`, `EmailTakenError`, `InvalidCredentialsError`, `SESSION_LIFETIME`.

## Бизнес-правила
- email нормализуется (нижний регистр, без пробелов), уникален (`src/kognis/users/_domain.py::normalize_email`);
- пароль ≥ 8 символов, хранится только хэш argon2id (`src/kognis/users/_infra.py::hash_password`);
- неверный пароль и неизвестный email неразличимы (`InvalidCredentialsError`);
- сессия — случайный токен; в БД только его SHA-256, срок 30 дней (`src/kognis/users/_domain.py::hash_token`), [ADR 0003](../adr/0003-auth-sessions-and-entry-protection.md).

## Данные (владение)
| Сущность / таблица | Владелец | Кто ещё читает | Кто может изменять |
|---|---|---|---|
| `User` / таблица `users` | `users` | `web` (через `UserService`) | только `users` (`src/kognis/users/_app.py::UserService.register`) |
| сессии / таблица `sessions` | `users` | — | только `users` (`src/kognis/users/_app.py::UserService.start_session`) |

## Внешние зависимости
- `db` — подключение и общий `metadata`; таблицы и запросы — `src/kognis/users/_infra.py::UserRepository`; схема — миграции `migrations/versions/`.
- `argon2-cffi` — хэш пароля.

## Проверка
- `just test-module users`

## Решения
- ADR: [0001](../adr/0001-record-architecture-decisions.md), [0003](../adr/0003-auth-sessions-and-entry-protection.md)
