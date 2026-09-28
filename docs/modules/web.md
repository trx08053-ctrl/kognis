# Модуль `web`

> Публичные символы и зависимости — `just context web`.

- **Назначение:** HTTP-вход приложения — JSON API `/api/*`, `/health` и раздача сборки интерфейса
  (`frontend/dist`). Бизнес-логики и SQL не содержит. Интерфейс — `frontend/` (React + TypeScript).
- **Публичный API:** `src/kognis/web/__init__.py` — `create_app`, `main`.

## Бизнес-правила
- ошибки валидации сценариев → 422 с JSON `detail`; интерфейс показывает его с `role="alert"`;
- типы ответов API повторены в `frontend/src/api.ts` — меняешь схему, меняй и их (tsc поймает расхождение в использовании);
- модули вызываются только через их публичный API;
- интерфейс: тема по умолчанию как в системе, явный выбор — в localStorage (`frontend/src/theme.ts`; палитра тёмной темы — `style.css`);
  режим Advanced (графики `Charts.tsx`, фильтры записей) хранится в профиле: `PUT /api/me/settings`; главная `/` — итог дня, форма, последние записи.

## Данные (владение)
| Сущность / таблица | Владелец | Кто ещё читает | Кто может изменять |
|---|---|---|---|
| — (своих данных нет) | — | `User` через `UserService` | — |

## Внешние зависимости
- `users`, `db` (публичные API); FastAPI; интерфейс — React, Vite.

## Проверка
- `just test-module web`; в браузере — `just e2e`, скриншоты — `just shot /`.
- интерфейс: `just fe-check` (Biome, tsc strict, vitest, сборка); тесты компонентов — `frontend/src/*.test.tsx`.

## Решения
- ADR: [0001](../adr/0001-record-architecture-decisions.md)
