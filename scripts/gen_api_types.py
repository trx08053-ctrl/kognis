#!/usr/bin/env python3
"""Типы API для фронтенда из OpenAPI бэкенда → frontend/src/api.gen.ts. Файл защищён.

    gen_api_types.py          сгенерировать заново (после изменения схем FastAPI)
    gen_api_types.py --check  проверка verify `contract`: файл совпадает со схемой бэкенда

Фронтенд берёт типы только отсюда (`components["schemas"]["UserOut"]`): переименование поля
на бэкенде ломает `tsc`, а не пользователя в браузере. Генератор свой (без компилятора TypeScript):
объекты, массивы, enum, nullable, ссылки, словари — этого хватает для схем Pydantic.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "src" / "api.gen.ts"
HEADER = "// auto-generated: scripts/gen_api_types.py из OpenAPI бэкенда — не редактировать\n"
DUMP = (
    "import json, sys\n"
    "from kognis.db import make_engine\n"
    "from kognis.web import create_app\n"
    "json.dump(create_app(make_engine('sqlite://')).openapi(), open(sys.argv[1], 'w'))\n"
)
SCALARS = {"string": "string", "integer": "number", "number": "number", "boolean": "boolean"}


def ref_name(ref: str) -> str:
    return f'components["schemas"]["{ref.rsplit("/", 1)[-1]}"]'


def literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def ts_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return ref_name(str(schema["$ref"]))
    if "const" in schema:
        return literal(schema["const"])
    if "enum" in schema:
        return " | ".join(literal(v) for v in schema["enum"])
    variants = schema.get("anyOf") or schema.get("oneOf")
    if variants:
        return " | ".join(dict.fromkeys(ts_type(s) for s in variants))
    return structural(schema)


def structural(schema: dict[str, Any]) -> str:
    kind = schema.get("type")
    if kind == "array":
        return f"({ts_type(schema.get('items', {}))})[]"
    if kind == "object" or "properties" in schema:
        extra = schema.get("additionalProperties")
        if not schema.get("properties") and isinstance(extra, dict):
            return f"Record<string, {ts_type(cast('dict[str, Any]', extra))}>"
        return object_type(schema, "    ")
    return "null" if kind == "null" else SCALARS.get(str(kind), "unknown")


def object_type(schema: dict[str, Any], indent: str) -> str:
    required = {str(n) for n in schema.get("required", [])}
    props = cast("dict[str, dict[str, Any]]", schema.get("properties", {}))
    if not props:
        return "Record<string, unknown>"
    lines = [
        f"{indent}  {json.dumps(n)}{'' if n in required else '?'}: {ts_type(s)};"
        for n, s in props.items()
    ]
    return "{\n" + "\n".join(lines) + f"\n{indent}}}"


def render(spec: dict[str, Any]) -> str:
    schemas = spec.get("components", {}).get("schemas", {})
    body = "\n".join(
        f"    {name}: {object_type(s, '    ') if s.get('type') == 'object' else ts_type(s)};"
        for name, s in sorted(schemas.items())
    )
    return HEADER + "export interface components {\n  schemas: {\n" + body + "\n  };\n}\n"


def current() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "openapi.json"
        dump = ["uv", "run", "--locked", "python", "-c", DUMP, str(spec)]
        subprocess.run(dump, cwd=ROOT, check=True)
        return render(json.loads(spec.read_text()))


def main() -> int:
    fresh = current()
    if "--check" not in sys.argv:
        OUT.write_text(fresh)
        print(f"типы API: {OUT.relative_to(ROOT)}")
        return 0
    if not OUT.exists() or OUT.read_text() != fresh:
        print("frontend/src/api.gen.ts устарел относительно схем API — `just api-types`, затем tsc")
        return 1
    print("contract: ok (типы фронтенда = схема OpenAPI бэкенда)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
