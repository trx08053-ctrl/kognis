# PROGRESS kognis-i7j

## Сделано
- `frontend/src/i18n` (Catalog, I18nProvider, useI18n, translate, formatDate, formatNumber, isKey, detectLocale;
  ru.ts), провайдер в main.tsx, `<html lang dir>`, `LanguageSwitcher` в профиле (скрыт при 1 языке), текст вынесен
  из App, main, Shell, Progress, Charts, HelpPanel, ErrorMessage, privateCrypto (ключи ошибок), логические
  свойства в style.css.
- Осознанные изменения видимого: дата «Получено:» через Intl («1 сент. 2026 г.»); тесты App.test.tsx, test_ui.py,
  privateCrypto.test.ts обновлены под формат/ключ.
- Тесты: `frontend/src/i18n.test.tsx`, `tests/web/test_i18n_frontend.py` (AC1–AC3), `tests/e2e/test_ui.py` (AC4).
- Доказательство: `just verify` зелёный, tree 2b248e384532; ревью approve (REVIEW.md).

## Следующий шаг
`python3 scripts/task.py done kognis-i7j`.
