@AGENTS.md

## Специфика Claude Code
- Subagents (`.claude/agents/`): `explorer` — широкий поиск без правок; `reviewer` — ревью в чистом контексте перед «готово».
- Параллельные задачи — только в отдельной рабочей копии (`just wt-new <id>` или `claude --worktree`), у каждой своя задача `bd`; перед слиянием — `just integrate <ветки>`.
- Hooks (`.claude/settings.json`): SessionStart показывает состояние; PreToolUse защищает файлы проверок и запрещает обход git hooks; Stop не даёт закончить с непроверенным кодом; все действия пишутся в `.agent-log/`. Не обходи их. Если hook мешает правомерной работе, скажи об этом человеку.
