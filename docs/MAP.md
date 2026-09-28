# Карта проекта

> Генерируется `just map` из кода — не редактировать вручную. `just check map` проверяет
> актуальность. Архитектурные правила — [ARCHITECTURE.md](ARCHITECTURE.md),
> границы — `.importlinter`.

Корневой пакет: `kognis` · компонентов: 9

## Компоненты

| Компонент | Назначение | Зависит от | Файлов | Карточка |
|---|---|---|---|---|
| `kognis.access` | Модуль access: TODO ответственность (одно предложение). | — | 4 | [access](modules/access.md) |
| `kognis.ai` | Модуль ai: единый интерфейс к языковой модели; провайдер выбирается настройкой. | — | 4 | [ai](modules/ai.md) |
| `kognis.analysis` | Модуль analysis: TODO ответственность (одно предложение). | — | 4 | [analysis](modules/analysis.md) |
| `kognis.db` | Платформа данных: подключение, метаданные таблиц, транзакции. | — | 1 | [db](modules/db.md) |
| `kognis.diary` | Модуль diary: записи дневника и итоги дня; владеет `entries` и `day_reviews`. | `db` | 4 | [diary](modules/diary.md) |
| `kognis.gameplay` | Модуль gameplay: опыт, уровни, серия дней, достижения (D8); владеет `xp_events` и др. | `db` | 4 | [gameplay](modules/gameplay.md) |
| `kognis.safety` | Модуль safety: кризисные сигналы в тексте (локально, без ИИ) и контакты помощи. | — | 4 | [safety](modules/safety.md) |
| `kognis.users` | Модуль users: регистрация, вход, сессии. Владеет данными пользователей и сессий. | `db` | 4 | [users](modules/users.md) |
| `kognis.web` | Модуль web: HTTP-вход приложения — страницы, JSON API, /health. Бизнес-логики не содержит. | `db`, `diary`, `gameplay`, `safety`, `users` | 2 | [web](modules/web.md) |

## `kognis.access`

- Код: `src/kognis/access`
- Публичный интерфейс: —
- Тесты: **нет**

## `kognis.ai`

- Код: `src/kognis/ai`
- Публичный интерфейс:
  - `AiError` — `src/kognis/ai/_domain.py`
  - `AiProvider` — `src/kognis/ai/_domain.py`
  - `AiTimeoutError` — `src/kognis/ai/_domain.py`
  - `FakeProvider` — `src/kognis/ai/_infra.py`
  - `HttpSettings` — `src/kognis/ai/_infra.py`
  - `Message` — `src/kognis/ai/_domain.py`
  - `OpenAICompatibleProvider` — `src/kognis/ai/_infra.py`
  - `get_provider` — `src/kognis/ai/_app.py`
- Тесты: `tests/ai/test_ai.py`

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
- Публичный интерфейс:
  - `ACHIEVEMENTS` — `src/kognis/gameplay/_domain.py`
  - `AchievementDef` — `src/kognis/gameplay/_domain.py`
  - `EarnedAchievement` — `src/kognis/gameplay/_domain.py`
  - `GameplayService` — `src/kognis/gameplay/_app.py`
  - `Progress` — `src/kognis/gameplay/_domain.py`
- Тесты: `tests/gameplay/test_domain.py`

## `kognis.safety`

- Код: `src/kognis/safety`
- Публичный интерфейс:
  - `DISCLAIMER` — `src/kognis/safety/_domain.py`
  - `Assessment` — `src/kognis/safety/_domain.py`
  - `Contact` — `src/kognis/safety/_domain.py`
  - `HelpBlock` — `src/kognis/safety/_app.py`
  - `assess` — `src/kognis/safety/_domain.py`
  - `check_text` — `src/kognis/safety/_app.py`
  - `help_block` — `src/kognis/safety/_app.py`
- Тесты: `tests/safety/test_safety.py`

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
- Тесты: `tests/web/test_day_reviews.py`, `tests/web/test_gameplay.py`, `tests/web/test_http.py`

## Точки входа

- `kognis` → `kognis.web:main`
