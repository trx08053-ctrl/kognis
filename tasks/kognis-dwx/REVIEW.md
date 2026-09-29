# REVIEW kognis-dwx

## Раунд 1 (коммит c34bbee)

VERDICT: changes

Bash у reviewer был недоступен: diff, vitest, tsc и verify он не запускал. Blocker нет.

### MAJOR
- Нет REVIEW.md → создан этим файлом.
- Сохранность поведения и `data-testid` не доказана → **сделано:** множество `data-testid` до (931934a: App.tsx, Quests.tsx, Charts.tsx) и после (`frontend/src`, без тестов) совпадает — 39 идентификаторов, различий нет (`git grep -o` / Grep). `git diff --stat 931934a HEAD -- frontend/src/App.test.tsx tests/e2e` пуст: существующие сценарии не тронуты. `just verify` OK (tree 14d59901a41a), `just e2e` — 21 passed.

### MINOR (не блокируют)
- `Diary` из TASK §2 отдельной страницы не имеет: дневник — это `HomePage` + `pages/home/*` (форма и список записей).
- Типы тел запросов (`saveSettings`, `register` и др.) в `api.ts` написаны вручную; AC2 касается ответов. Улучшение вынесено из границ задачи.
- `parse<T>` делает `as T` без проверки во время выполнения — прежнее ограничение, вне границ задачи.
- Проверка AC2 в тесте не строгая (пропустит `type X = Foo & {…}`); принято.
- Выход из аккаунта в jsdom-тесте проверяет только запрос logout; логика `client.clear()` + `invalidateQueries` перенесена в `Shell` без изменений (лог. идентична прежней).
- Планка поднята через `just ratchet-up` (ветвления 80.75 %).

### NOT CHECKED
- Побайтовая эквивалентность разметки старого и нового кода (проверены только testid, тесты и e2e).
- Актуальность `api.gen.ts` относительно бэкенда — проверка `contract` в verify зелёная.
