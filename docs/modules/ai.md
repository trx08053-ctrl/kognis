# Модуль `ai`

> Ссылки на код — `` `src/<пакет>/<модуль>/<файл>.py::<символ>` `` (проверяет `just check refs`).
> Публичные символы и фактические зависимости генерируются: `just context ai` / `docs/MAP.md`.

- **Назначение:** единый интерфейс к языковой модели (`complete(system, messages, schema?) -> str`); провайдер выбирается настройкой. Не строит промпты и не разбирает ответы — это делает `analysis`.
- **Публичный API:** только `src/kognis/ai/__init__.py` (`__all__`); файлы `_*.py` — внутренности.

## Бизнес-правила
- Без `KOGNIS_AI_BASE_URL` — `FakeProvider` (детерминированный, без сети): `src/kognis/ai/_app.py::get_provider`.
- `OpenAICompatibleProvider` (`KOGNIS_AI_BASE_URL`, `KOGNIS_AI_MODEL`, `KOGNIS_AI_API_KEY`): запрос chat/completions, повтор при 429/5xx с растущей паузой (2 повтора), таймаут → `AiTimeoutError`, прочее → `AiError`: `src/kognis/ai/_infra.py::OpenAICompatibleProvider`.
- Текст `AiError` называет категорию причины: адрес не найден (DNS), соединение отклонено, таймаут, HTTP-код с
  пояснением (401/403 — ключ отклонён, 404, 429, 5xx — сбой провайдера): `src/kognis/ai/_infra.py::http_failure`.
- Ключ API не попадает в логи, `repr` и тексты ошибок; тела ответов провайдера в ошибки не включаются.

## Данные (владение)
Собственных данных нет.

## Внешние зависимости
- OpenAI-совместимый HTTP API (Ollama Cloud, vLLM и др.); недоступен → `AiError`, вызывающий показывает «попробуйте позже».

## Проверка
- `just test-module ai` — тесты модуля на `httpx.MockTransport` и его границы.

## Решения
- `docs/DECISIONS-NIGHT.md` D6.
