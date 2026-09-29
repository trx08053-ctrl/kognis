# Модуль `diary`

> Публичные символы и фактические зависимости генерируются: `just context diary` / `docs/MAP.md`.

- **Назначение:** записи дневника (текст, теги, эмоции, дата) и итоги дня (самочувствие, настроение, рефлексия) их владельца. Не отвечает за аккаунты, ИИ-анализ и игровую механику.
- **Публичный API:** `src/kognis/diary/__init__.py` — `DiaryService`, `Entry`, `DayReview`.

## Бизнес-правила
- текст записи не пуст и ≤ 20 000 символов (`src/kognis/diary/_domain.py::normalize_text`);
- теги и эмоции — нижний регистр, без пустых и повторов, ≤ 20 штук (`src/kognis/diary/_domain.py::normalize_labels`);
- каждая операция принимает владельца; чужая запись неотличима от несуществующей — `None` (`src/kognis/diary/_app.py::DiaryService.get_entry`);
- выборка за период: `list_entries_between` и `list_day_reviews_between` — границы включительно, фильтр по владельцу и датам в SQL-запросе (`src/kognis/diary/_app.py::DiaryService.list_entries_between`); `analysis` использует их, а не грузит всё и не фильтрует в Python;
- итог дня: самочувствие и настроение — целые 1–10, рефлексия ≤ 5 000 символов (может быть пустой); один итог на владельца и дату, повторное сохранение исправляет его (`src/kognis/diary/_app.py::DiaryService.save_day_review`);
- запись с кризисным сигналом помечается флагом `crisis` (`src/kognis/diary/_app.py::DiaryService.mark_crisis`); сам сигнал находит `safety`, сценарий связывает `web`; запись сохраняется всегда;
- режимы защиты: `plain`, `locked` («под замком») и `private` ([ADR 0003](../adr/0003-auth-sessions-and-entry-protection.md));
- `locked`: текст шифруется AES-GCM ключом `KOGNIS_DATA_KEY` (base64, 32 байта; AAD — владелец и версия формата), в `entries.text` пусто, шифртекст/nonce/версия — `lock_*`; пароль замка (≥ 8 символов) — argon2id-хэш (`src/kognis/diary/_crypto.py`);
- `private` («приватная», kognis-8f1): текст шифруется в браузере (WebCrypto: PBKDF2-SHA256, 600 000 итераций → AES-GCM-256, `frontend/src/privateCrypto.ts`); сервер получает и хранит только конверт `{v, kdf, iter, salt, iv, ct}` в `entries.private_envelope`, `text` пуст. `DiaryService.create_private_entry` проверяет лишь форму конверта (версия 1, KDF, ≥ 600 000 итераций, размеры соли/iv/данных) — прочитать содержимое сервер не может; пароль на сервер не передаётся и не восстанавливается (забыт — запись потеряна). Конверт отдаётся владельцу в `cipher` (список и `get_entry`), расшифровка — в браузере. В анализ такие записи не попадают (`analysis` берёт только `plain`); кризисный детектор видит только теги и эмоции (текста у сервера нет);
- в списках и `get_entry` у закрытой записи текст пуст; текст отдаёт только `open_entry` с паролем на время запроса, в БД он не расшифровывается. Ошибки: `WrongLockPasswordError` (неверный пароль), `EntryUnreadableError` (ключ данных сменился), `DataKeyError` (ключ не задан/некорректен) — тексты без содержимого записи;
- `lock_entry` закрывает обычную запись, `unlock_entry` (с паролем) снимает замок; в анализ закрытые записи не попадают (`analysis` берёт только `plain`). Забытый пароль замка не восстанавливается;
- честные границы (D4): пароль замка — проверка доступа (argon2id), ключ шифрования — только `KOGNIS_DATA_KEY`, поэтому владелец БД **вместе с ключом** читает записи; шифруется лишь текст — теги, эмоции, дата и флаг кризиса остаются открытыми; `web` ограничивает неверные пароли (5 за 5 минут на запись, в памяти процесса → 429) и отдаёт открытый текст с `Cache-Control: no-store`.

## Данные (владение)
| Сущность / таблица | Владелец | Кто ещё читает | Кто может изменять |
|---|---|---|---|
| `Entry` / таблица `entries` | `diary` | `web` (через `DiaryService`) | только `diary` (`src/kognis/diary/_app.py::DiaryService.create_entry`) |
| `DayReview` / таблица `day_reviews` (уникально `owner_id`+`review_date`) | `diary` | `web` (через `DiaryService`) | только `diary` (`src/kognis/diary/_app.py::DiaryService.save_day_review`) |

`owner_id` — id пользователя из `users`, внешнего ключа нет: таблицей `users` владеет другой модуль.

## Внешние зависимости
- `db` — подключение и `metadata`; таблица — `src/kognis/diary/_infra.py::EntryRepository`; схема — миграции.

## Проверка
- `just test-module diary` — тесты модуля и его границы; сценарий U1 — `tests/e2e/`.

## Решения
- ADR: [0003](../adr/0003-auth-sessions-and-entry-protection.md)
