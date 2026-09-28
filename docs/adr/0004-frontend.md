# 0004. Интерфейс: React Router, TanStack Query, Tailwind

- **Статус:** Accepted (jusk-one по делегированию, 2026-09-29; см. docs/DECISIONS-NIGHT.md D10)
- **Дата:** 2026-09-29 · **Задача:** kognis-b8z

## Контекст
Нужен современный интерфейс с тёмной темой, простым и Advanced-режимами и графиками.

## Решение
React + TypeScript (strict, без `any`), React Router (маршруты), TanStack Query (кэш запросов к `/api/*`),
Tailwind CSS v4 (стили, тёмная тема через класс `dark`), Recharts (графики Advanced). Язык — русский, строки в
одном месте. Клиент ходит только в `/api/*` с cookie сессии.

## Проверка результата
`just fe-check`, e2e в браузере, axe без serious/critical.

## Последствия
- **Минусы:** больше зависимостей фронтенда.
- **Когда пересмотреть:** смена фреймворка UI.
