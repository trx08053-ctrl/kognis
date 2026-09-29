# Фронтенд React + TypeScript (frontend/). Подключается из web.just.

# Фронтенд: Biome + tsc strict + vitest + сборка (то же, что `just check frontend`)
fe-check:
    pnpm --dir frontend run check

# Фронтенд с горячей перезагрузкой на :5173 (API проксируется на бэкенд `just dev`)
fe-dev:
    pnpm --dir frontend dev --host

# Типы API фронтенда из схемы бэкенда (после изменения схем FastAPI; проверка verify `contract`)
api-types:
    python3 scripts/gen_api_types.py
