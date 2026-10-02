# Карта проекта

> Генерируется `just map` из кода — не редактировать вручную. `just check map` проверяет
> актуальность. Архитектурные правила — [ARCHITECTURE.md](ARCHITECTURE.md),
> границы — `.importlinter`.

Корневой пакет: `kognis` · компонентов: 10

## Компоненты

| Компонент | Назначение | Зависит от | Файлов | Карточка |
|---|---|---|---|---|
| `kognis.access` | Модуль access: решает, доступна ли пользователю функция (D9); сейчас — всегда да. | — | 4 | [access](modules/access.md) |
| `kognis.ai` | Модуль ai: единый интерфейс к языковой модели; провайдер выбирается настройкой. | `errors` | 4 | [ai](modules/ai.md) |
| `kognis.analysis` | Модуль analysis: ИИ-анализ периода по направлениям и динамика настроения; владеет `analyses`. | `ai`, `db`, `diary`, `errors`, `safety` | 5 | [analysis](modules/analysis.md) |
| `kognis.db` | Платформа данных: подключение, метаданные таблиц, транзакции. | — | 1 | [db](modules/db.md) |
| `kognis.diary` | Модуль diary: записи дневника и итоги дня; владеет `entries` и `day_reviews`. | `db`, `errors` | 5 | [diary](modules/diary.md) |
| `kognis.errors` | Ошибки для показа человеку: код и параметры вместо фразы (docs/I18N.md, правило 2). | — | 1 | [errors](modules/errors.md) |
| `kognis.gameplay` | Модуль gameplay: опыт, уровни, серия, достижения, квесты, квизы (D8). | `db`, `errors` | 17 | [gameplay](modules/gameplay.md) |
| `kognis.safety` | Модуль safety: кризисные сигналы в тексте (локально, без ИИ) и контакты помощи. | — | 4 | [safety](modules/safety.md) |
| `kognis.users` | Модуль users: регистрация, вход, сессии. Владеет данными пользователей и сессий. | `db`, `errors` | 4 | [users](modules/users.md) |
| `kognis.web` | Модуль web: HTTP-вход приложения — страницы, JSON API, /health. Бизнес-логики не содержит. | `access`, `ai`, `analysis`, `db`, `diary`, `errors`, `gameplay`, `safety`, `users` | 17 | [web](modules/web.md) |

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
- Тесты: `tests/ai/test_ai.py`, `tests/analysis/test_analysis.py`, `tests/analysis/test_continuity.py`, `tests/analysis/test_crisis_detector_off.py`, `tests/analysis/test_history.py`, `tests/diary/test_period.py`, `tests/e2e/test_analysis_history.py`, `tests/e2e/test_heroes.py`, `tests/e2e/test_ui.py`, `tests/security/test_idor.py`, `tests/web/test_achievements.py`, `tests/web/test_companion.py`, `tests/web/test_private.py`, `tests/web/test_quests.py`, `tests/web/test_timezone.py`

## `kognis.analysis`

- Код: `src/kognis/analysis`
- Публичный интерфейс:
  - `DEFAULT_PAGE_SIZE` — `src/kognis/analysis/_domain.py`
  - `DIRECTIONS` — `src/kognis/analysis/_domain.py`
  - `MAX_PAGE_SIZE` — `src/kognis/analysis/_domain.py`
  - `Analysis` — `src/kognis/analysis/_domain.py`
  - `AnalysisFailedError` — `src/kognis/analysis/_app.py`
  - `AnalysisOutcome` — `src/kognis/analysis/_app.py`
  - `AnalysisPage` — `src/kognis/analysis/_app.py`
  - `AnalysisResult` — `src/kognis/analysis/_domain.py`
  - `AnalysisService` — `src/kognis/analysis/_app.py`
  - `ConsentRequiredError` — `src/kognis/analysis/_app.py`
  - `Direction` — `src/kognis/analysis/_domain.py`
  - `DuplicateAnalysisError` — `src/kognis/analysis/_app.py`
  - `MoodDynamics` — `src/kognis/analysis/_domain.py`
  - `MoodPoint` — `src/kognis/analysis/_domain.py`
  - `NoDataError` — `src/kognis/analysis/_app.py`
  - `Pattern` — `src/kognis/analysis/_domain.py`
  - `PeriodSuggestion` — `src/kognis/analysis/_domain.py`
- Тесты: `tests/ai/test_ai_eval.py`, `tests/analysis/test_analysis.py`, `tests/analysis/test_crisis_detector_off.py`, `tests/diary/test_period.py`, `tests/security/test_domain_limits.py`, `tests/users/test_error_code_units.py`, `tests/web/test_achievements.py`

## `kognis.db`

- Код: `src/kognis/db`
- Публичный интерфейс:
  - `database_url` — `src/kognis/db/__init__.py`
  - `make_engine` — `src/kognis/db/__init__.py`
  - `metadata` — `src/kognis/db/__init__.py`
  - `transaction` — `src/kognis/db/__init__.py`
- Тесты: `tests/diary/test_boundaries.py`, `tests/diary/test_diary.py`, `tests/diary/test_period.py`, `tests/e2e/test_sparks.py`, `tests/gameplay/test_heroes.py`, `tests/gameplay/test_migration_0016.py`, `tests/gameplay/test_migration_0017.py`, `tests/gameplay/test_migration_0018.py`, `tests/gameplay/test_migration_0019.py`, `tests/gameplay/test_migration_0020.py`, `tests/gameplay/test_mutants.py`, `tests/gameplay/test_quests.py`, `tests/gameplay/test_service.py`, `tests/gameplay/test_sparks.py`, `tests/gameplay/test_xp_balance.py`, `tests/gameplay/test_xp_ownership.py`, `tests/integration/test_postgres.py`, `tests/users/test_locale.py`, `tests/users/test_users.py`, `tests/web/test_achievements.py`, `tests/web/test_hardening.py`, `tests/web/test_sparks.py`

## `kognis.diary`

- Код: `src/kognis/diary`
- Публичный интерфейс:
  - `DEFAULT_PAGE_SIZE` — `src/kognis/diary/_domain.py`
  - `MAX_PAGE_SIZE` — `src/kognis/diary/_domain.py`
  - `MIN_LOCK_PASSWORD` — `src/kognis/diary/_crypto.py`
  - `DataKeyError` — `src/kognis/diary/_crypto.py`
  - `DayReview` — `src/kognis/diary/_domain.py`
  - `DiaryService` — `src/kognis/diary/_app.py`
  - `Entry` — `src/kognis/diary/_domain.py`
  - `EntryDraft` — `src/kognis/diary/_domain.py`
  - `EntryFilter` — `src/kognis/diary/_domain.py`
  - `EntryUnreadableError` — `src/kognis/diary/_crypto.py`
  - `InvalidCursorError` — `src/kognis/diary/_domain.py`
  - `Page` — `src/kognis/diary/_domain.py`
  - `WrongLockPasswordError` — `src/kognis/diary/_crypto.py`
- Тесты: `tests/diary/test_boundaries.py`, `tests/diary/test_diary.py`, `tests/diary/test_label_filter_sql.py`, `tests/diary/test_period.py`, `tests/integration/test_postgres.py`, `tests/security/test_domain_limits.py`, `tests/users/test_error_code_units.py`, `tests/web/test_day_reviews.py`

## `kognis.errors`

- Код: `src/kognis/errors.py`
- Публичный интерфейс:
  - `CodedError` — `src/kognis/errors.py`
  - `CodedValueError` — `src/kognis/errors.py`
- Тесты: `tests/gameplay/test_heroes.py`, `tests/users/test_error_code_units.py`

## `kognis.gameplay`

- Код: `src/kognis/gameplay`
- Публичный интерфейс:
  - `ACHIEVEMENTS` — `src/kognis/gameplay/_domain.py`
  - `ACHIEVEMENT_SPARKS` — `src/kognis/gameplay/_sparks.py`
  - `APPEARANCES` — `src/kognis/gameplay/_heroes.py`
  - `SHOP` — `src/kognis/gameplay/_sparks.py`
  - `SPARK_QUEST` — `src/kognis/gameplay/_sparks.py`
  - `SPARK_WEEKLY_GOAL` — `src/kognis/gameplay/_sparks.py`
  - `AchievementDef` — `src/kognis/gameplay/_domain.py`
  - `AlreadyAcceptedError` — `src/kognis/gameplay/_quests.py`
  - `CompanionState` — `src/kognis/gameplay/_heroes_app.py`
  - `DailyDoneTodayError` — `src/kognis/gameplay/_daily_infra.py`
  - `DailyState` — `src/kognis/gameplay/_daily.py`
  - `EarnedAchievement` — `src/kognis/gameplay/_domain.py`
  - `FreezeStockFullError` — `src/kognis/gameplay/_sparks_app.py`
  - `GameplayService` — `src/kognis/gameplay/_app.py`
  - `HeroLine` — `src/kognis/gameplay/_heroes.py`
  - `HeroService` — `src/kognis/gameplay/_heroes_app.py`
  - `MentorState` — `src/kognis/gameplay/_heroes_app.py`
  - `NotEnoughSparksError` — `src/kognis/gameplay/_sparks_infra.py`
  - `OwnedItemError` — `src/kognis/gameplay/_sparks_infra.py`
  - `Postcard` — `src/kognis/gameplay/_heroes.py`
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
  - `RecoveryOffer` — `src/kognis/gameplay/_domain.py`
  - `RecoveryUnavailableError` — `src/kognis/gameplay/_app.py`
  - `ShopItem` — `src/kognis/gameplay/_sparks.py`
  - `ShopPosition` — `src/kognis/gameplay/_sparks_app.py`
  - `SparkRepository` — `src/kognis/gameplay/_sparks_infra.py`
  - `SparksService` — `src/kognis/gameplay/_sparks_app.py`
  - `SparksState` — `src/kognis/gameplay/_sparks_app.py`
  - `StepOutcome` — `src/kognis/gameplay/_quests.py`
  - `StepUnavailableError` — `src/kognis/gameplay/_quests.py`
  - `achievement_sparks` — `src/kognis/gameplay/_sparks.py`
  - `item_by_code` — `src/kognis/gameplay/_sparks.py`
  - `purchase_ref` — `src/kognis/gameplay/_sparks.py`
- Тесты: `tests/e2e/test_sparks.py`, `tests/gameplay/test_daily.py`, `tests/gameplay/test_domain.py`, `tests/gameplay/test_heroes.py`, `tests/gameplay/test_migration_0016.py`, `tests/gameplay/test_migration_0017.py`, `tests/gameplay/test_migration_0018.py`, `tests/gameplay/test_migration_0019.py`, `tests/gameplay/test_migration_0020.py`, `tests/gameplay/test_mutants.py`, `tests/gameplay/test_quests.py`, `tests/gameplay/test_service.py`, `tests/gameplay/test_sparks.py`, `tests/gameplay/test_streak_model.py`, `tests/gameplay/test_xp_balance.py`, `tests/gameplay/test_xp_ownership.py`, `tests/integration/test_postgres.py`, `tests/security/test_domain_limits.py`, `tests/web/test_achievements.py`, `tests/web/test_gameplay.py`, `tests/web/test_sparks.py`

## `kognis.safety`

- Код: `src/kognis/safety`
- Публичный интерфейс:
  - `DISCLAIMER` — `src/kognis/safety/_domain.py`
  - `Assessment` — `src/kognis/safety/_domain.py`
  - `Contact` — `src/kognis/safety/_domain.py`
  - `HelpBlock` — `src/kognis/safety/_app.py`
  - `assess` — `src/kognis/safety/_domain.py`
  - `check_text` — `src/kognis/safety/_app.py`
  - `crisis_detector_enabled` — `src/kognis/safety/_infra.py`
  - `help_block` — `src/kognis/safety/_app.py`
- Тесты: `tests/ai/test_ai_eval.py`, `tests/analysis/test_analysis.py`, `tests/analysis/test_crisis_detector_off.py`, `tests/safety/test_safety.py`

## `kognis.users`

- Код: `src/kognis/users`
- Публичный интерфейс:
  - `DEFAULT_LOCALE` — `src/kognis/users/_domain.py`
  - `DEFAULT_TIMEZONE` — `src/kognis/users/_domain.py`
  - `MAX_LOCALE_LENGTH` — `src/kognis/users/_domain.py`
  - `SESSION_LIFETIME` — `src/kognis/users/_app.py`
  - `SUPPORTED_LOCALES` — `src/kognis/users/_domain.py`
  - `EmailTakenError` — `src/kognis/users/_domain.py`
  - `InvalidCredentialsError` — `src/kognis/users/_domain.py`
  - `LoginBlockedError` — `src/kognis/users/_domain.py`
  - `User` — `src/kognis/users/_domain.py`
  - `UserService` — `src/kognis/users/_app.py`
  - `pick_locale` — `src/kognis/users/_domain.py`
- Тесты: `tests/integration/test_postgres.py`, `tests/security/test_domain_limits.py`, `tests/users/test_error_code_units.py`, `tests/users/test_users.py`, `tests/web/test_hardening.py`

## `kognis.web`

- Код: `src/kognis/web`
- Публичный интерфейс:
  - `create_app` — `src/kognis/web/_app.py`
  - `main` — `src/kognis/web/__init__.py`
- Тесты: `tests/analysis/test_analysis.py`, `tests/analysis/test_continuity.py`, `tests/analysis/test_crisis_detector_off.py`, `tests/analysis/test_history.py`, `tests/e2e/test_analysis_history.py`, `tests/e2e/test_heroes.py`, `tests/e2e/test_sparks.py`, `tests/e2e/test_ui.py`, `tests/security/test_body_limit.py`, `tests/security/test_errors.py`, `tests/security/test_idor.py`, `tests/security/test_locale_access.py`, `tests/users/test_locale.py`, `tests/web/test_achievements.py`, `tests/web/test_archive.py`, `tests/web/test_companion.py`, `tests/web/test_crisis_review.py`, `tests/web/test_daily_quest.py`, `tests/web/test_day_reviews.py`, `tests/web/test_error_codes.py`, `tests/web/test_gameplay.py`, `tests/web/test_hardening.py`, `tests/web/test_http.py`, `tests/web/test_locked.py`, `tests/web/test_motivation.py`, `tests/web/test_operations.py`, `tests/web/test_private.py`, `tests/web/test_quests.py`, `tests/web/test_sparks.py`, `tests/web/test_timezone.py`

## Точки входа

- `kognis` → `kognis.web:main`
