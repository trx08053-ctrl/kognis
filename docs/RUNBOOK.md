# Runbook Kognis

## Запуск
```bash
just setup
just dev                  # приложение с автоперезагрузкой; настройки — .deploy/dev.app.env
```

## Секреты
См. [secrets/README.md](../secrets/README.md).

## Релиз (решение человека)
1. `just next-version` → предложенная версия по коммитам.
2. `just release X.Y.Z` → verify, CHANGELOG, версия, тег.
3. `git push --follow-tags`.

## Откат
- Код: `just rollback [--env production --host ssh://…]` — предыдущий образ из истории окружения.
- Данные: `just restore .deploy/backups/<env>-<время>.dump [--env …]` — только если релиз повредил данные;
  миграции — expand → migrate → contract, чтобы откат образа не требовал восстановления.

## Развёртывание, бэкап, восстановление
```bash
just stage                                        # staging на этом хосте (образ из HEAD, Trivy, миграции, /health)
just backup                                       # дамп PostgreSQL → .deploy/backups/staging-<время>.dump (600)
just restore .deploy/backups/staging-….dump       # остановить app → восстановить → /health
APP_BIND=127.0.0.1 just deploy --host ssh://deploy@srv --port 8000       # прод — решение человека
just backup --env production --host ssh://deploy@srv                      # перед каждым деплоем со схемой
```
- `/health` проверяет и базу данных: при недоступной БД деплой не пройдёт.
- Секреты окружения — `.deploy/<env>.env` (пароль БД) и `.deploy/<env>.app.env` (ключи приложения); дамп
  их не содержит — храните копии отдельно (менеджер паролей).
- Восстановление репетирует `just selftest-deploy` в шаблоне; в проекте — репетируйте на staging.

## Инциденты
| Дата | Что случилось | Причина | Исправление | Предотвращение |
|---|---|---|---|---|

## Ключ данных для записей «под замком»
- `KOGNIS_DATA_KEY` — base64 от 32 случайных байт: `python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`. В проде — из секретов (`secrets/README.md`), не в git и не в логи.
- Без ключа приложение работает, а замок отвечает 503 «ключ данных не задан». **Потеря или смена ключа делает все закрытые записи нечитаемыми** (ответ 409 «ключ данных изменился»); ключ бэкапить отдельно от БД. Ротации ключа пока нет.
- Забытый пароль замка восстановить нельзя.
- `deploy/compose.yml` пока **не передаёт** `KOGNIS_DATA_KEY` в контейнер `app` (защищённый файл, правка — решение человека): добавить `KOGNIS_DATA_KEY: ${KOGNIS_DATA_KEY:-}` в `environment` сервиса `app`, иначе в развёртывании замок отвечает 503.

## Бэкап и восстановление (PostgreSQL)
Проект compose называется `<slug>-<env>` (для stage — `kognis-stage`; `docker compose -p … ps` покажет точное имя).
```bash
# бэкап: дамп БД (в нём зашифрованные закрытые записи и хэши паролей — хранить как секрет)
docker compose -p kognis-stage -f deploy/compose.yml exec -T db pg_dump -U app -Fc app > kognis-$(date +%F).dump
# восстановление (app остановить, затем вернуть)
docker compose -p kognis-stage -f deploy/compose.yml stop app
docker compose -p kognis-stage -f deploy/compose.yml exec -T db pg_restore -U app -d app --clean --if-exists < kognis-YYYY-MM-DD.dump
docker compose -p kognis-stage -f deploy/compose.yml up -d app
```
- Дамп **не содержит** `KOGNIS_DATA_KEY`: без ключа закрытые записи из восстановленной БД не открываются. Бэкапьте ключ отдельно от дампа (в другом хранилище секретов).
- «Приватные» записи шифруются в браузере: их не прочитать ни из дампа, ни с ключом.
- После восстановления: `curl /health`, вход тестовым пользователем, открытие закрытой записи; при старом дампе — `alembic upgrade head`. Восстановление стоит периодически репетировать на копии.

## Защита входа и заголовки
- Вход: 5 неудачных попыток на email или 20 на IP за 15 минут → ответ 429 с `Retry-After`. Попытки — таблица `login_attempts` (переживает перезапуск); успешный вход сбрасывает счётчик email. Срочно разблокировать: `DELETE FROM login_attempts WHERE email = '…'`.
- IP берётся из соединения. За обратным прокси все запросы будут «с одного IP» и лимит 20 заблокирует всех: перед публикацией за прокси нужно передавать реальный IP (uvicorn `--proxy-headers` + доверенные адреса) — отдельной задачей.
- Заголовки (CSP `default-src 'self'` без inline, `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, HSTS вне dev) выставляет приложение (`SECURITY_HEADERS` в `src/kognis/web/_app.py`). Новый внешний ресурс (шрифты, аналитика, CDN) требует осознанного расширения CSP.
- HSTS включён при `KOGNIS_ENV` ≠ `dev`: приложение должно стоять за https.

## Приватность логов
- Тексты записей, теги, пароли замка и итоги дня не логируются; `make_engine` включает `hide_parameters`, поэтому ошибки БД не несут значения запросов. Проверка — `tests/web/test_hardening.py` (AC3).
- Нельзя включать `echo=True`/SQL-логи движка и отладочный лог тела запросов в проде.
