# PROGRESS kognis-yaj

<!-- Статус задачи — только в bd (`bd show <id>`). Здесь — передача контекста: обновлять после каждого шага. -->

## Следующий шаг
Разобрать замечания reviewer (blocker/major — устранить), затем `python3 scripts/task.py done kognis-yaj`.
`just stage` не запускался: у агента нет доступа к docker.sock (см. «Блокеры») — прогнать человеку.

## Сделано
| Дата | Шаг | Коммит | Evidence / проверка |
|---|---|---|---|
| 2026-09-29 | Ограничение входа: 5/email и 20/IP за 15 мин, таблица `login_attempts` (миграция 0011), 429 + Retry-After (AC1) | ec122be | verify OK, tree ae3ea94a416e |
| 2026-09-29 | Заголовки безопасности (CSP и др., HSTS вне dev), `hide_parameters` в `make_engine`, тесты AC2/AC3, e2e под CSP + axe + скриншот | f1e0e3f | verify OK, tree 52ba41b97acd |
| 2026-09-29 | RUNBOOK: ключ данных, бэкап/восстановление, вход и заголовки, приватность логов | см. git log | verify OK |

## Блокеры и вопросы человеку
- `just stage` не выполнен: `permission denied … /var/run/docker.sock` (вне выданных агенту прав). Прогнать `just stage` вручную.
- `deploy/compose.yml` (защищённый файл) не передаёт `KOGNIS_DATA_KEY` в контейнер `app` — добавить `KOGNIS_DATA_KEY: ${KOGNIS_DATA_KEY:-}` (записано в RUNBOOK).
- За обратным прокси лимит по IP требует реального IP клиента (`--proxy-headers`) — отдельной задачей (RUNBOOK).

## Попытки и гипотезы (что пробовали и почему не сработало)
- Тест AC3 сначала упал: текст записи попадал в текст ошибки БД (параметры запроса) → `hide_parameters=True`.

## Затраты
Сессии: 1 · $~1.6 · время ~1 ч
