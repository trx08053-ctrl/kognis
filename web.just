# Веб-стек (подключается из justfile через `import? 'web.just'`). Подробности: python3 scripts/web.py -h
import? 'frontend.just'

# Сервер разработки с автоперезагрузкой (миграции применяются автоматически)
dev *args:
    python3 scripts/web.py dev {{args}}

# Скриншот страницы работающего приложения → .evidence/screens/ (агент открывает PNG и видит интерфейс)
shot *args:
    python3 scripts/web.py shot {{args}}

# Браузер Chromium для e2e и скриншотов (один раз)
setup-browsers:
    python3 scripts/web.py browsers

# e2e-сценарии в браузере
e2e *args:
    if [ -d frontend ]; then pnpm --dir frontend build >/dev/null; fi
    uv run --locked pytest -m e2e --no-cov {{args}}

# Интеграция с PostgreSQL (нужен Docker)
test-int *args:
    uv run --locked pytest -m integration --no-cov {{args}}

# Миграции: применить / создать новую по изменениям моделей
db-upgrade:
    uv run --locked alembic upgrade head

db-revision message:
    uv run --locked alembic revision --autogenerate -m "{{message}}"

# Развёртывание в Docker на этом хосте (staging): образ из HEAD, PostgreSQL, миграции, /health
stage *args:
    python3 scripts/web.py stage {{args}}

# Откат staging на предыдущий образ
rollback *args:
    python3 scripts/web.py rollback {{args}}

# Развёртывание на сервер (решение человека): just deploy --host ssh://deploy@server
deploy *args:
    python3 scripts/web.py deploy {{args}}

deploy-status *args:
    python3 scripts/web.py status {{args}}

stage-down *args:
    python3 scripts/web.py down {{args}}

# Бэкап PostgreSQL окружения → .deploy/backups/ (хранить как секрет); восстановление — решение человека
backup *args:
    python3 scripts/web.py backup {{args}}

restore file *args:
    python3 scripts/web.py restore {{file}} {{args}}
