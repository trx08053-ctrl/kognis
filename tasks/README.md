# Задачи

Граф задач и статусы — в Beads (`bd ready`, `bd show <id>`, экспорт в `.beads/issues.jsonl`).
Для нетривиальных задач здесь хранится рабочая папка `tasks/<bd-id>/`:

- `TASK.md` — постановка по [шаблону](../docs/templates/TASK.md);
- `PROGRESS.md` — журнал и следующий шаг по [шаблону](../docs/templates/PROGRESS.md).

```bash
just task-new "Название" --type feature        # bd create + tasks/<id>/TASK.md, PROGRESS.md
just task-start <id>                           # in_progress
just task-block <id> "что нужно от человека"   # blocked
just task-done <id>                            # закрыть — только при успешном evidence
just tasks                                     # в работе (со следующим шагом) и готовые
just agent-run --task <id>                     # автономно, с лимитами бюджета/времени/повторов
```

Продолжение после прерывания: состояние в git + bd + PROGRESS.md. Новая сессия Claude получает
сводку (SessionStart), Stop-hook не даёт закончить без обновлённого PROGRESS.md после коммитов.
`agent_run.py` запускает сессии заново, пока задача не закрыта/заблокирована или не исчерпаны лимиты
(журнал: `.agent-log/runs.jsonl`).
