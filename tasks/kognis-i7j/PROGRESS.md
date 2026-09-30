# PROGRESS kognis-i7j

## Сделано
- Сессия 1: TASK.md; `frontend/src/i18n` (index.tsx: Catalog, I18nProvider, useI18n, translate, formatDate,
  formatNumber, isKey, detectLocale; ru.ts); провайдер в main.tsx; `<html lang dir>`; `LanguageSwitcher` в профиле
  (скрыт при 1 языке); текст вынесен из App, main, Shell, Progress, Charts, HelpPanel, ErrorMessage (ключи ошибок),
  privateCrypto (ошибки — ключи); style.css — логические свойства.
- Осознанные изменения видимого: дата «Получено:» — через Intl («1 сент. 2026 г.», было ISO) — тест App.test.tsx
  обновлён; `privateCrypto.test.ts` ждёт ключ ошибки (текст — в словаре).
- Тесты: `frontend/src/i18n.test.tsx` (AC2, AC3), `tests/web/test_i18n_frontend.py` (AC1–AC3),
  `tests/e2e/test_ui.py::test_shell_texts_unchanged_after_i18n` (AC4).

## Следующий шаг
`just verify` → коммит → reviewer (REVIEW.md) → `python3 scripts/task.py done kognis-i7j` (сам делает ratchet-up).
