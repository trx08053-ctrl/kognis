# Единая точка входа для человека, агента и CI. Файл защищён.
set shell := ["bash", "-euo", "pipefail", "-c"]

# рецепты веб-стека (есть только в проектах stack=web)
import? 'web.just'

default:
    @just --list --unsorted

# Поднять окружение с нуля
setup:
    mise install
    uv sync --locked
    lefthook install
    python3 scripts/check_security.py update
    bd init --non-interactive --skip-agents --skip-hooks --init-if-missing -q
    @just status

# Версии инструментов и состояние
doctor:
    @for t in uv just lefthook gitleaks lychee git-cliff bd ast-grep; do printf "%-10s %s\n" $t "$($t --version 2>&1 | head -1)"; done
    @just status

# Все проверки + evidence (обязательно перед «готово»)
verify:
    python3 scripts/verify.py

# Выбранные проверки без evidence: just check lint types
check *names:
    python3 scripts/verify.py {{names}}

# Есть ли evidence для текущего состояния кода
status:
    @python3 scripts/verify.py --status || true

# Автоформатирование и автоисправления
fmt:
    uv run --locked ruff format src tests scripts .claude/hooks
    uv run --locked ruff check --fix src tests scripts .claude/hooks

lint:
    uv run --locked ruff check src tests scripts .claude/hooks

types:
    uv run --locked basedpyright

# Тесты: just test tests/test_core.py -k greet
test *args:
    uv run --locked pytest {{args}}

# Быстрые тесты без integration/e2e и без покрытия
test-fast *args:
    uv run --locked pytest -m "not integration and not e2e" --no-cov {{args}}

# Поднять планку качества до текущих значений (только вверх) после зелёного verify
ratchet-up:
    python3 scripts/check_ratchet.py --update

# Документация: ссылки, ссылки на код, карта (если есть)
docs-check:
    python3 scripts/verify.py docs refs $(test -f docs/MAP.md && echo map)

# Перегенерировать карту проекта docs/MAP.md из кода
map:
    python3 scripts/gen_map.py

# Новый бизнес-модуль + карточка: just module-new billing
module-new name:
    python3 scripts/new_module.py {{name}}

# Компактный контекст модуля: карточка + API, зависимости, тесты, ADR из кода
context name:
    @python3 scripts/context.py {{name}}

# Быстрая проверка одного модуля (тесты + границы); вердикт готовности — только verify
test-module name *args:
    @python3 scripts/test_module.py {{name}} {{args}}

# Сверка заявленной области задачи с фактическими изменениями (сигналы для ревью)
scope id:
    @python3 scripts/check_scope.py {{id}}

# Регрессионный тест падает на прежнем коде? just regress tests/x/test_bug.py [--ref <коммит>]
regress *args:
    @python3 scripts/regress.py {{args}}

# Карточка для существующего компонента
module-card name:
    python3 scripts/new_module.py {{name}} --card-only

# Уязвимости зависимостей (офлайн-база; обновление — just security-update)
audit:
    python3 scripts/check_security.py deps

# Мутационное тестирование изменений задачи: ловят ли тесты поломку кода (в task-done — для risky)
mutate id:
    python3 scripts/check_mutation.py {{id}}

# Обновить наборы правил Semgrep и базу уязвимостей (нужна сеть; раз в неделю — автоматически при setup)
security-update:
    python3 scripts/check_security.py update --force

# Задачи: новая / начать / заблокировать / закрыть (только с evidence) / в работе
task-new title *flags:
    @python3 scripts/task.py new "{{title}}" {{flags}}

task-start id:
    @python3 scripts/task.py start {{id}}

# kind: needs_input | budget | infra | no_progress
task-block id reason kind="needs_input":
    @python3 scripts/task.py block {{id}} "{{reason}}" --kind {{kind}}

# Закрыть задачу; человек может указать своё время: just task-done <id> --human-min 20
task-done id *flags:
    @python3 scripts/task.py done {{id}} {{flags}}

tasks:
    @python3 scripts/task.py list
    @bd ready

# Автономный прогон агента по задаче с лимитами: just agent-run --task ID --total-budget 5
agent-run *flags:
    python3 scripts/agent_run.py {{flags}}

# Затраты и ошибки агента: just costs --days 30
costs *args:
    @python3 scripts/costs.py {{args}}

# UI-замечания кликом: прокси с оверлеем перед приложением → tasks/<id>/ui-feedback.md
ui-feedback id target="http://localhost:5173" port="7777":
    python3 scripts/ui_feedback.py {{id}} --target {{target}} --port {{port}}

# Второе мнение другой модели (Ollama Cloud, код уходит во внешнее облако): just review-x --task ID
review-x *flags:
    @python3 scripts/second_opinion.py {{flags}}

# Параллельная работа: своя рабочая копия на задачу (общий bd)
wt-new id:
    @python3 scripts/worktree.py new {{id}}

wt-list:
    @python3 scripts/worktree.py list

wt-remove id:
    @python3 scripts/worktree.py remove {{id}}

# Параллельные агенты: just wt-run id1 id2 -- --backend ollama --total-budget 4
wt-run *args:
    python3 scripts/worktree.py run {{args}}

# Проверка объединённого результата веток (временная integration/*, merge в main — человек)
integrate *branches:
    python3 scripts/worktree.py integrate {{branches}}

# Текущая ветка: rebase на свежий main и verify
sync-main:
    git fetch origin main 2>/dev/null || true
    git rebase "$(git rev-parse --verify -q origin/main || echo main)"
    python3 scripts/verify.py

# Черновик CHANGELOG для неопубликованных изменений
changelog:
    git cliff --unreleased

# Следующая версия по Conventional Commits
next-version:
    git cliff --bumped-version

# Выпуск релиза (только человек): обновить CHANGELOG, версию и тег
release version:
    python3 scripts/verify.py
    uv version {{version}}
    git cliff --tag v{{version}} -o CHANGELOG.md
    git add CHANGELOG.md pyproject.toml uv.lock
    git commit -m "chore(release): v{{version}}"
    git tag -a v{{version}} -m "v{{version}}"
