# Модуль `users`

> Публичные символы и фактические зависимости — `just context users`.

- **Назначение:** регистрация и поиск пользователей. Не отвечает за приветствия и права доступа.
- **Публичный API:** `src/kognis/users/__init__.py` — `User`, `UserService`.

## Бизнес-правила
- имя пользователя без пробелов по краям, пустое имя недопустимо (`src/kognis/users/_domain.py::normalize_name`);
- id выдаются последовательно при регистрации.

## Данные (владение)
| Сущность / таблица | Владелец | Кто ещё читает | Кто может изменять |
|---|---|---|---|
| `User` / таблица `users` | `users` | `web` (через `UserService`) | только `users` (`src/kognis/users/_app.py::UserService.register`) |

## Внешние зависимости
- `db` — подключение и общий `metadata`; таблица и запросы — `src/kognis/users/_infra.py::UserRepository`; схема — миграции `migrations/versions/`.

## Проверка
- `just test-module users`

## Решения
- ADR: [0001](../adr/0001-record-architecture-decisions.md)
