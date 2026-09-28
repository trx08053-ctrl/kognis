# Runbook Kognis

## Запуск
```bash
just setup
uv run python -c "import kognis; print(kognis.greet('dev'))"
```

## Секреты
См. [secrets/README.md](../secrets/README.md).

## Релиз (решение человека)
1. `just next-version` → предложенная версия по коммитам.
2. `just release X.Y.Z` → verify, CHANGELOG, версия, тег.
3. `git push --follow-tags`.

## Откат
- Код: деплой предыдущего тега `vX.Y.Z`.
- Данные: восстановление из бэкапа (описать, когда появится хранилище); миграции — только expand → migrate → contract.

## Инциденты
| Дата | Что случилось | Причина | Исправление | Предотвращение |
|---|---|---|---|---|
