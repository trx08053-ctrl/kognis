# REVIEW kognis-zjg — раунд 1 (2026-10-01)

```
VERDICT: request-changes
EVIDENCE: verified — verify.py --status OK (tree 9d9f1b8aca44, evidence ok:true, head 47847f8 — прогон был
до коммита фронтенда, текущее дерево 355b907 совпадает по tree_hash); ревьюером прогнаны
tests/gameplay/test_heroes.py + tests/web/test_companion.py + test_structure.py + test_heroes_frontend.py
(28 passed) и vitest src/heroes.test.tsx (8 passed); скриншоты e2e (4 шт., светлая/тёмная) лежат в
.evidence/screens; сам e2e не перезапускал.
BLOCKERS:  (нет)
MAJOR:
     - frontend/src/components/Heroes.tsx:294,298 — множественное число никогда не выбирается:
       вызывается t("hero.days.other", {count}) / t("hero.next.other", {count}), а translate
       (frontend/src/i18n/index.tsx) подставляет форму как "<ключ>.<plural>", т.е. ищет
       hero.days.other.many — такого ключа нет, всегда падает на текст hero.days.other
       «{count} дня с дневником». Проверено симуляцией translate: «5 дня с дневником»,
       «9 дня с дневником», «1 дня с дневником» — неверная форма для большинства чисел; ключи
       hero.days.one/few/many и hero.next.one/few/many (ru.ts) мёртвые. Нарушение docs/I18N.md
       правило 3 (подтверждено образцом t("shell.streak", {count}) в i18n.test.tsx).
       Исправление: базовые ключи hero.days / hero.next, вызывать t("hero.days", {count}).
     - migrations/versions/0018_motivation_heroes.py — заявленный в TASK 2b тест миграции 0018
       отсутствует: у 0016 и 0017 есть tests/gameplay/test_migration_*.py с @pytest.mark.migration
       (прогон на данных прошлой версии), для 0018 аналога нет; на это же указывает check_scope.py.
       Добавить: upgrade 0017→0018 на существующих данных + downgrade удаляет только
       companions/companion_postcards.
MINOR:
     - frontend/src/pages/QuestsPage.tsx:104 — MentorLine не скрывается при кризисном ответе квиза:
       QuizCard рендерит result.help (контакты помощи) на том же экране, реплика наставника остаётся.
       Вопрос автору: добить или завести bd.
     - src/kognis/gameplay/_heroes_infra.py:71 — save_companion: гонка двух параллельных PUT
       (первое знакомство из двух вкладок) даёт IntegrityError по PK owner_id → 500; рядом в
       _reviews.py аналогичный случай обрабатывается повтором. UI защищён (disabled при isPending).
     - src/kognis/web/_companion.py:47 — GET /api/companion пишет в БД (создаёт открытку).
       Намеренно (AC2, задокументировано в карточке gameplay.md) — осознанный побочный эффект.
     - src/kognis/gameplay/_heroes_app.py:127 — template_by_code(quest.template_code) может кинуть
       CodedValueError для квеста, чей шаблон удалён из библиотеки QUESTS → 500 на GET /api/companion.
       Сейчас шаблоны не удаляются, риск гипотетический.
NOT CHECKED: полный just verify (e2e, mutants, postgres-интеграцию) не перезапускал — полагается на
evidence; перформанс GET /api/companion на объёме года; визуальная оценка SVG/скриншотов.
```

Пояснения ревьюера:
1. Plural-баг проверен симуляцией translate (node): «9 дня с дневником». Чинится без изменения translate — базовыми ключами `hero.days`/`hero.next`.
2. Тест миграции — единственное расхождение TASK ↔ факт; сам файл миграции корректен (expand, downgrade удаляет только две новые таблицы), поэтому major, не blocker.
3. Ослаблений проверок нет; правка tests/web/test_structure.py (8→9 роутеров) легитимна.
4. Безопасность: маршруты под Authed, фильтр по owner_id, IDOR-поверхности нет, SQL параметризован, экранирование React.
5. Архитектура и область: владение таблицами обновлено, web зовёт героев только через публичный API kognis.gameplay.