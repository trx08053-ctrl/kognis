"""Лимит размера тела запроса (API4, ASVS V13): слишком большое тело отклоняется с 413."""

import json
import time

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Самое большое законное тело — конверт приватной записи (~160 КБ шифртекста в base64)
MAX_BODY_BYTES = 512 * 1024
TOO_LARGE = json.dumps({"detail": "слишком большой запрос"}, ensure_ascii=False).encode()

LOCK_ATTEMPTS = 5  # неверных паролей замка на запись за окно, затем 429
LOCK_ATTEMPT_WINDOW = 300.0


class BodyLimitMiddleware:
    """Чистый ASGI: считает байты и при заявленном (Content-Length), и при потоковом теле."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self.reject(send)
            return

        received = 0
        exceeded = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message: Message) -> None:
            if exceeded and message["type"] == "http.response.start":
                await self.reject(send)
            elif not exceeded:
                await send(message)

        await self.app(scope, limited_receive, guarded_send)

    async def reject(self, send: Send) -> None:
        headers = [(b"content-type", b"application/json"), (b"connection", b"close")]
        await send({"type": "http.response.start", "status": 413, "headers": headers})
        await send({"type": "http.response.body", "body": TOO_LARGE})


class AttemptLimiter:
    """Неверные пароли замка по (владелец, запись); в памяти процесса (TD-8)."""

    def __init__(self) -> None:
        self._failures: dict[tuple[int, int], list[float]] = {}

    def _recent(self, key: tuple[int, int]) -> list[float]:
        now = time.monotonic()
        return [t for t in self._failures.get(key, []) if now - t < LOCK_ATTEMPT_WINDOW]

    def check(self, key: tuple[int, int]) -> None:
        if len(self._recent(key)) >= LOCK_ATTEMPTS:
            raise HTTPException(status_code=429, detail="слишком много попыток, попробуйте позже")

    def fail(self, key: tuple[int, int]) -> None:
        self._failures[key] = [*self._recent(key), time.monotonic()]

    def reset(self, key: tuple[int, int]) -> None:
        self._failures.pop(key, None)
