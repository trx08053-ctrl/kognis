# Карта проекта

> Генерируется `just map` из кода — не редактировать вручную. `just check map` проверяет
> актуальность. Архитектурные правила — [ARCHITECTURE.md](ARCHITECTURE.md),
> границы — `.importlinter`.

Корневой пакет: `kognis` · компонентов: 9

## Компоненты

| Компонент | Назначение | Зависит от | Файлов | Карточка |
|---|---|---|---|---|
| `kognis.access` | Модуль access: решает, доступна ли пользователю функция (D9); сейчас — всегда да. | — | 4 | [access](modules/access.md) |
| `kognis.ai` | Модуль ai: единый интерфейс к языковой модели; провайдер выбирается настройкой. | — | 4 | [ai](modules/ai.md) |
| `kognis.analysis` | Модуль analysis: ИИ-анализ периода по направлениям и динамика настроения; владеет `analyses`. | `ai`, `db`, `diary`, `safety` | 4 | [analysis](modules/analysis.md) |
| `kognis.db` | Платформа данных: подключение, метаданные таблиц, транзакции. | — | 1 | [db](modules/db.md) |
| `kognis.diary` | Модуль diary: записи дневника и итоги дня; владеет `entries` и `day_reviews`. | `db` | 5 | [diary](modules/diary.md) |
| `kognis.gameplay` | Модуль gameplay: опыт, уровни, серия, достижения, квесты, квизы (D8). | `db` | 7 | [gameplay](modules/gameplay.md) |
| `kognis.safety` | Модуль safety: кризисные сигналы в тексте (локально, без ИИ) и контакты помощи. | — | 4 | [safety](modules/safety.md) |
| `kognis.users` | Модуль users: регистрация, вход, сессии. Владеет данными пользователей и сессий. | `db` | 4 | [users](modules/users.md) |
| `kognis.web` | Модуль web: HTTP-вход приложения — страницы, JSON API, /health. Бизнес-логики не содержит. | `access`, `ai`, `analysis`, `db`, `diary`, `gameplay`, `safety`, `users` | 3 | [web](modules/web.md) |

## `kognis.access`

- Код: `src/kognis/access`
- Публичный интерфейс:
  - `Feature` — `src/kognis/access/_domain.py`
  - `can_use` — `src/kognis/access/_domain.py`
- Тесты: `tests/analysis/test_analysis.py`

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
- Тесты: `tests/ai/test_ai.py`, `tests/analysis/test_analysis.py`, `tests/e2e/test_ui.py`, `tests/security/test_idor.py`, `tests/web/test_private.py`, `tests/web/test_quests.py`, `tests/web/test_timezone.py`

## `kognis.analysis`

- Код: `src/kognis/analysis`
- Публичный интерфейс:
  - `DIRECTIONS` — `src/kognis/analysis/_domain.py`
  - `Analysis` — `src/kognis/analysis/_domain.py`
  - `AnalysisFailedError` — `src/kognis/analysis/_app.py`
  - `AnalysisOutcome` — `src/kognis/analysis/_app.py`
  - `AnalysisResult` — `src/kognis/analysis/_domain.py`
  - `AnalysisService` — `src/kognis/analysis/_app.py`
  - `ConsentRequiredError` — `src/kognis/analysis/_app.py`
  - `Direction` — `src/kognis/analysis/_domain.py`
  - `MoodDynamics` — `src/kognis/analysis/_domain.py`
  - `MoodPoint` — `src/kognis/analysis/_domain.py`
  - `NoDataError` — `src/kognis/analysis/_app.py`
  - `Pattern` — `src/kognis/analysis/_domain.py`
- Тесты: `tests/analysis/test_analysis.py`, `tests/security/test_domain_limits.py`

## `kognis.db`

- Код: `src/kognis/db`
- Публичный интерфейс:
  - `database_url` — `src/kognis/db/__init__.py`
  - `make_engine` — `src/kognis/db/__init__.py`
  - `metadata` — `src/kognis/db/__init__.py`
  - `transaction` — `src/kognis/db/__init__.py`
- Тесты: `tests/diary/test_diary.py`, `tests/gameplay/test_quests.py`, `tests/gameplay/test_service.py`, `tests/integration/test_postgres.py`, `tests/users/test_users.py`, `tests/web/test_hardening.py`

## `kognis.diary`

- Код: `src/kognis/diary`
- Публичный интерфейс:
  - `MIN_LOCK_PASSWORD` — `src/kognis/diary/_crypto.py`
  - `DataKeyError` — `src/kognis/diary/_crypto.py`
  - `DayReview` — `src/kognis/diary/_domain.py`
  - `DiaryService` — `src/kognis/diary/_app.py`
  - `Entry` — `src/kognis/diary/_domain.py`
  - `EntryDraft` — `src/kognis/diary/_domain.py`
  - `EntryUnreadableError` — `src/kognis/diary/_crypto.py`
  - `WrongLockPasswordError` — `src/kognis/diary/_crypto.py`
- Тесты: `tests/diary/test_diary.py`, `tests/integration/test_postgres.py`, `tests/security/test_domain_limits.py`, `tests/web/test_day_reviews.py`

## `kognis.gameplay`

- Код: `src/kognis/gameplay`
- Публичный интерфейс:
  - `ACHIEVEMENTS` — `src/kognis/gameplay/_domain.py`
  - `AchievementDef` — `src/kognis/gameplay/_domain.py`
  - `AlreadyAcceptedError` — `src/kognis/gameplay/_quests.py`
  - `EarnedAchievement` — `src/kognis/gameplay/_domain.py`
  - `GameplayService` — `src/kognis/gameplay/_app.py`
  - `Progress` — `src/kognis/gameplay/_domain.py`
  - `Quest` — `src/kognis/gameplay/_quests.py`
  - `QuestService` — `src/kognis/gameplay/_quests_app.py`
  - `QuestStep` — `src/kognis/gameplay/_quests.py`
  - `QuestTemplate` — `src/kognis/gameplay/_quests.py`
  - `QuizAnswers` — `src/kognis/gameplay/_quests.py`
  - `QuizDef` — `src/kognis/gameplay/_quests.py`
  - `QuizDoneTodayError` — `src/kognis/gameplay/_quests.py`
  - `QuizOutcome` — `src/kognis/gameplay/_quests.py`
  - `QuizStatus` — `src/kognis/gameplay/_quests.py`
  - `StepOutcome` — `src/kognis/gameplay/_quests.py`
  - `StepUnavailableError` — `src/kognis/gameplay/_quests.py`
- Тесты: `tests/gameplay/test_domain.py`, `tests/gameplay/test_quests.py`, `tests/gameplay/test_service.py`, `tests/security/test_domain_limits.py`

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
  - `DEFAULT_TIMEZONE` — `src/kognis/users/_domain.py`
  - `SESSION_LIFETIME` — `src/kognis/users/_app.py`
  - `EmailTakenError` — `src/kognis/users/_domain.py`
  - `InvalidCredentialsError` — `src/kognis/users/_domain.py`
  - `LoginBlockedError` — `src/kognis/users/_domain.py`
  - `User` — `src/kognis/users/_domain.py`
  - `UserService` — `src/kognis/users/_app.py`
- Тесты: `tests/integration/test_postgres.py`, `tests/security/test_domain_limits.py`, `tests/users/test_users.py`, `tests/web/test_hardening.py`

## `kognis.web`

- Код: `src/kognis/web`
- Публичный интерфейс:
  - `create_app` — `src/kognis/web/_app.py`
  - `main` — `src/kognis/web/__init__.py`
- Тесты: `tests/analysis/test_analysis.py`, `tests/e2e/test_ui.py`, `tests/security/test_body_limit.py`, `tests/security/test_errors.py`, `tests/security/test_idor.py`, `tests/web/test_crisis_review.py`, `tests/web/test_day_reviews.py`, `tests/web/test_gameplay.py`, `tests/web/test_hardening.py`, `tests/web/test_http.py`, `tests/web/test_locked.py`, `tests/web/test_private.py`, `tests/web/test_quests.py`, `tests/web/test_timezone.py`

## Точки входа

- `kognis` → `kognis.web:main`
