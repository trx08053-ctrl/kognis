# REVIEW kognis-zjg — раунд 2 (2026-10-01)

```
VERDICT: approve
EVIDENCE: verified — scripts/verify.py --status → .evidence/973fed9145714dab185ef0d98f879db440e5ce13.json
  (ok:true, head f0bd195, tree 973fed914571, dirty:false, 554 passed, все 20 проверок exit 0).
  HEAD fc3b8cf отличается от проверенного head только tasks/kognis-zjg/PROGRESS.md (документация),
  код идентичен проверенному дереву. Ревьюером прогнаны локально: pytest test_migration_0018.py +
  test_heroes.py + test_companion.py (25 passed), vitest (95 passed, включая 9 heroes),
  check_scope.py kognis-zjg — «расхождений нет», check_i18n — ok.
BLOCKERS:  (нет)
MAJOR:     (нет — оба из раунда 1 устранены)
MINOR:
     - frontend/src/i18n/ru.ts:226,231 — hero.days.other/hero.next.other недостижимы для целых
       count (Intl.PluralRules('ru') возвращает 'other' только для нецелых); текст дублирует
       базовый ключ. НЕ мёртвый код: docs/I18N.md правило 3 прямо требует полный набор
       one/few/many/other, а translate при отсутствии формы падает на базовый ключ.
       Информационно, правка не нужна.
     - Перенесено из раунда 1 (зафиксировано, не правилось): _heroes_infra.py:85 гонка двух
       параллельных первых PUT /api/companion → IntegrityError → 500 (UI защищён disabled);
       _heroes_app.py:133 template_by_code гипотетически может дать 500 при удалении шаблона
       из библиотеки. Кризисный минор корректно вынесен в bd kognis-wov (status open).
NOT CHECKED: e2e/axe и скриншоты не перезапускались (evidence + .evidence/screens); полный
  just verify не повторял (только evidence); интеграция Postgres; перформанс GET /api/companion
  на истории в год; визуальное качество SVG-героев (только по коду и тестам).
```

Проверка устранения major из раунда 1:
1. Plural (f1fca80) — устранён по существу: симуляция translate по реальному коду и каталогу: 1 → «день» (one), 2 → «дня» (few), 5 → «дней» (many), 21 → «день» (one), 0 → «дней» (many). Регресс-тест покрывает one/many; few-форма не покрыта, но механизм единый (`forms[form] ?? text`).
2. Тест миграции 0018 (bf14735) — поведение, не реализация: данные xp_events на схеме 0017 → upgrade 0018 → HeroService работает на старых данных (days_total == 4) → downgrade удаляет только новые таблицы, xp_events целы. Конвенция 0017-теста соблюдена.
3. Остальной дифф: f0bd195 — MAP.md, fc3b8cf — PROGRESS.md; замечаний нет.

---

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