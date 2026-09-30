"""Ответы API об ошибках: `{"detail": {"code": "...", "params": {...}}}` (docs/I18N.md)."""

from typing import Any

from fastapi import HTTPException

from kognis.errors import CodedError

GENERIC_CODE = "request.invalid"  # ошибка без кода (не для показа): текст исключения наружу не идёт


def error_detail(code: str, **params: Any) -> dict[str, Any]:
    return {"code": code, "params": params}


def http_error(
    status_code: int,
    error: CodedError | ValueError | str,
    headers: dict[str, str] | None = None,
    **params: Any,
) -> HTTPException:
    """HTTP-ошибка по доменной ошибке с кодом или по коду; чужое исключение — общий код."""
    if isinstance(error, str):
        detail = error_detail(error, **params)
    elif isinstance(error, CodedError):
        detail = error_detail(error.code, **error.params)
    else:
        detail = error_detail(GENERIC_CODE)
    return HTTPException(status_code=status_code, detail=detail, headers=headers)
