"""BodyLimitMiddleware на уровне ASGI: тело без Content-Length, пришедшее несколькими чанками."""

import asyncio
from typing import Any

from starlette.types import Message, Scope

from kognis.web._limits import BodyLimitMiddleware


def run(chunks: list[bytes], limit: int) -> list[Message]:
    async def app(scope: Scope, receive: Any, send: Any) -> None:
        while (await receive()).get("more_body"):
            pass
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    queue = [
        {"type": "http.request", "body": c, "more_body": i < len(chunks) - 1}
        for i, c in enumerate(chunks)
    ]
    sent: list[Message] = []

    async def receive() -> Message:
        return queue.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {"type": "http", "headers": []}
    asyncio.run(BodyLimitMiddleware(app, max_bytes=limit)(scope, receive, send))
    return sent


def test_chunks_summing_over_limit_give_413() -> None:
    sent = run([b"x" * 300, b"x" * 300, b"x" * 300], limit=500)
    assert sent[0]["status"] == 413


def test_chunks_within_limit_pass() -> None:
    sent = run([b"x" * 200, b"x" * 200], limit=500)
    assert sent[0]["status"] == 200
