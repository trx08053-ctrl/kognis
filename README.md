# Kognis

Дневник переживаний с ИИ-анализом по направлениям психологии и игровыми квестами

## Быстрый старт

Нужны: git, [mise](https://mise.jdx.dev), Docker (staging, интеграционные тесты); остальное ставит `just setup`.

```bash
just setup     # инструменты (mise), зависимости (uv, pnpm), git hooks (lefthook), задачи (bd)
just verify    # все проверки + evidence
just dev       # приложение: http://<хост>:8000
just           # список команд
```

**Настройки** — переменные окружения, список и значения по умолчанию — в
[RUNBOOK → Настройки](docs/RUNBOOK.md#настройки-переменные-окружения). Для `just dev` они лежат в
`.deploy/dev.app.env` (скрытая папка `.deploy`, не в git), для окружений — в `.deploy/<env>.app.env`.

## Документация

- [AGENTS.md](AGENTS.md) — правила работы (для людей и агентов)
- [Архитектура](docs/ARCHITECTURE.md) · [ADR](docs/adr/) · [Runbook](docs/RUNBOOK.md) · [Техдолг](docs/TECH_DEBT.md)
- [Harness: как устроен процесс](docs/HARNESS.md)
- [CHANGELOG](CHANGELOG.md)
