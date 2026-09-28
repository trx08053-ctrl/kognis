# Модуль `diary`

> Публичные символы и фактические зависимости генерируются: `just context diary` / `docs/MAP.md`.

- **Назначение:** записи дневника (текст, теги, эмоции, дата) их владельца. Не отвечает за аккаунты, ИИ-анализ и игровую механику.
- **Публичный API:** `src/kognis/diary/__init__.py` — `DiaryService`, `Entry`.

## Бизнес-правила
- текст записи не пуст и ≤ 20 000 символов (`src/kognis/diary/_domain.py::normalize_text`);
- теги и эмоции — нижний регистр, без пустых и повторов, ≤ 20 штук (`src/kognis/diary/_domain.py::normalize_labels`);
- каждая операция принимает владельца; чужая запись неотличима от несуществующей — `None` (`src/kognis/diary/_app.py::DiaryService.get_entry`);
- режим защиты пока только `plain` (`private`/`locked` — отдельные задачи, [ADR 0003](../adr/0003-auth-sessions-and-entry-protection.md)).

## Данные (владение)
| Сущность / таблица | Владелец | Кто ещё читает | Кто может изменять |
|---|---|---|---|
| `Entry` / таблица `entries` | `diary` | `web` (через `DiaryService`) | только `diary` (`src/kognis/diary/_app.py::DiaryService.create_entry`) |

`owner_id` — id пользователя из `users`, внешнего ключа нет: таблицей `users` владеет другой модуль.

## Внешние зависимости
- `db` — подключение и `metadata`; таблица — `src/kognis/diary/_infra.py::EntryRepository`; схема — миграции.

## Проверка
- `just test-module diary` — тесты модуля и его границы; сценарий U1 — `tests/e2e/`.

## Решения
- ADR: [0003](../adr/0003-auth-sessions-and-entry-protection.md)
