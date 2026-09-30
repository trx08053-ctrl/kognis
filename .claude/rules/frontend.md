---
paths:
  - "frontend/src/**"
---
# Интерфейс (подробно — docs/UI.md)
- TypeScript без `any`; типы API — только из `api.gen.ts` (`just api-types` после изменения схем бэкенда).
- Правка видна глазами: `just shot /путь` → открой PNG; сценарии — `just e2e`; `just fe-check`.
- Текст — только `t("ключ")` и ключ во всех `src/i18n/<язык>.ts`; ошибки сервера — по `code`; даты и числа — `formatDate`/`formatNumber`; в CSS — `*-inline-start/end` вместо left/right (docs/I18N.md).
