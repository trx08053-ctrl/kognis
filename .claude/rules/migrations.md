---
paths:
  - "migrations/**"
  - "src/**/_infra.py"
---
# Схема данных (подробно — docs/EVOLUTION.md)
- Схема — только миграциями: `just db-revision "…"`, проверь сгенерированный файл; проверка `migrations` ловит
  изменение модели без миграции.
- Изменение существующих данных — тест `@pytest.mark.migration` на данных прошлой версии; expand → migrate →
  contract, чтобы откат образа был безопасным.
