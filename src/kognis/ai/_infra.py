"""Хранение и внешние системы (адаптеры)."""

import hashlib
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from ._domain import AiError, AiTimeoutError, Message

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
BAD_FORMAT = "Провайдер ИИ вернул ответ в неожиданном формате"


class FakeProvider:
    """Детерминированный провайдер для тестов и dev: одинаковый вход — одинаковый ответ."""

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        schema: dict[str, Any] | None = None,
    ) -> str:
        payload = json.dumps([system, [(m.role, m.content) for m in messages]], ensure_ascii=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
        if schema is not None:
            return json.dumps({"fake": True, "digest": digest})
        return "[fake:" + digest + "] сообщений: " + str(len(messages))


@dataclass(frozen=True)
class HttpSettings:
    timeout: float = 60.0
    max_retries: int = 2
    backoff: float = 1.0
    sleep: Callable[[float], None] = time.sleep


class OpenAICompatibleProvider:
    """chat/completions по OpenAI-совместимому API (Ollama Cloud, vLLM и др.)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        settings: HttpSettings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._headers = {"Authorization": "Bearer " + api_key} if api_key else {}
        self._settings = settings or HttpSettings()
        self._transport = transport

    def __repr__(self) -> str:
        return f"OpenAICompatibleProvider(url={self._url!r}, model={self._model!r})"

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        schema: dict[str, Any] | None = None,
    ) -> str:
        chat = [{"role": "system", "content": system}]
        chat += [{"role": m.role, "content": m.content} for m in messages]
        body: dict[str, Any] = {"model": self._model, "messages": chat}
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": schema},
            }
        response = self._post(body)
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise AiError(BAD_FORMAT) from None
        if not isinstance(content, str):
            raise AiError(BAD_FORMAT)
        return content

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        cfg = self._settings
        with httpx.Client(timeout=cfg.timeout, transport=self._transport) as client:
            attempt = 0
            while True:
                try:
                    response = client.post(self._url, json=body, headers=self._headers)
                except httpx.TimeoutException:
                    msg = f"Провайдер ИИ не ответил за {cfg.timeout:g} с"
                    raise AiTimeoutError(msg) from None
                except httpx.HTTPError:
                    raise AiError("Не удалось связаться с провайдером ИИ") from None
                status = response.status_code
                if response.is_success:
                    return response
                if status not in RETRY_STATUSES or attempt >= cfg.max_retries:
                    raise AiError(f"Провайдер ИИ вернул ошибку {status}")
                log.warning("ai provider returned %s, retry %s", status, attempt + 1)
                cfg.sleep(cfg.backoff * 2**attempt)
                attempt += 1
