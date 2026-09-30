import json
import logging
import socket
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from kognis.ai import (
    AiError,
    AiTimeoutError,
    FakeProvider,
    HttpSettings,
    Message,
    OpenAICompatibleProvider,
    get_provider,
)

KEY = "sk-secret-123"
MESSAGES = [Message("user", "Привет")]

Handler = Callable[[httpx.Request], httpx.Response]


def make(
    handler: Handler,
    sleep: Callable[[float], None] = lambda _: None,
    **kwargs: Any,
) -> OpenAICompatibleProvider:
    settings = HttpSettings(sleep=sleep, **kwargs)
    return OpenAICompatibleProvider(
        "https://ai.example/v1/", "m1", KEY, settings, httpx.MockTransport(handler)
    )


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": "Ответ"}}]})


@pytest.mark.acceptance("kognis-1gr", "AC1")
def test_default_provider_is_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("KOGNIS_AI_BASE_URL", "KOGNIS_AI_MODEL", "KOGNIS_AI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    assert provider.complete("s", MESSAGES) == provider.complete("s", MESSAGES)
    assert provider.complete("s", MESSAGES) != provider.complete("s", [Message("user", "Другое")])
    assert json.loads(provider.complete("s", MESSAGES, {"type": "object"}))


@pytest.mark.acceptance("kognis-1gr", "AC1")
def test_env_selects_openai_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOGNIS_AI_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("KOGNIS_AI_MODEL", "m1")
    assert isinstance(get_provider(), OpenAICompatibleProvider)


@pytest.mark.acceptance("kognis-1gr", "AC2")
def test_request_and_response_parsing() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok(request)

    schema = {"type": "object"}
    assert make(handler).complete("Система", MESSAGES, schema) == "Ответ"
    request = seen[0]
    assert str(request.url) == "https://ai.example/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer " + KEY
    body = json.loads(request.content)
    assert body["model"] == "m1"
    assert body["messages"] == [
        {"role": "system", "content": "Система"},
        {"role": "user", "content": "Привет"},
    ]
    assert body["response_format"]["json_schema"]["schema"] == schema


@pytest.mark.acceptance("kognis-1gr", "AC2")
@pytest.mark.parametrize("status", [429, 503])
def test_retries_with_pause_then_succeeds(status: int) -> None:
    calls: list[int] = []
    pauses: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status) if len(calls) < 3 else ok(request)

    assert make(handler, sleep=pauses.append).complete("s", MESSAGES) == "Ответ"
    assert len(calls) == 3
    assert len(pauses) == 2
    assert pauses == [1.0, 2.0]


@pytest.mark.acceptance("kognis-1gr", "AC2")
def test_gives_up_after_retries_and_does_not_retry_client_errors() -> None:
    calls: list[int] = []

    def server_error(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    with pytest.raises(AiError, match=r"ai\.http_server") as failed:
        make(server_error).complete("s", MESSAGES)
    assert failed.value.params == {"status": 500}
    assert len(calls) == 3

    calls.clear()

    def bad_request(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400)

    with pytest.raises(AiError, match=r"ai\.http_rejected") as rejected:
        make(bad_request).complete("s", MESSAGES)
    assert rejected.value.params == {"status": 400}
    assert len(calls) == 1


@pytest.mark.acceptance("kognis-1gr", "AC2")
def test_timeout_gives_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AiTimeoutError, match=r"ai\.timeout"):
        make(handler, timeout=5).complete("s", MESSAGES)


@pytest.mark.acceptance("kognis-1gr", "AC2")
def test_malformed_response_is_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"oops": 1})

    with pytest.raises(AiError, match=r"ai\.bad_format"):
        make(handler).complete("s", MESSAGES)


@pytest.mark.acceptance("kognis-1gr", "AC3")
def test_key_not_in_logs_or_errors(caplog: pytest.LogCaptureFixture) -> None:
    texts: list[str] = []
    caplog.set_level(logging.DEBUG)

    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="echo " + request.headers["authorization"])

    def timing_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("t", request=request)

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("c", request=request)

    for handler in (failing, timing_out, broken):
        provider = make(handler)
        texts.append(repr(provider))
        with pytest.raises(AiError) as info:
            provider.complete("s", MESSAGES)
        texts += [str(info.value), repr(info.value)]
    texts.append(caplog.text)
    assert not any(KEY in t for t in texts)


def _failure(handler: Handler, **kwargs: Any) -> AiError:
    with pytest.raises(AiError) as info:
        make(handler, **kwargs).complete("s", MESSAGES)
    return info.value


@pytest.mark.acceptance("kognis-3fl", "AC3")
def test_error_names_the_failure_category_without_key() -> None:
    def dns(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request) from socket.gaierror(
            -2, "Name or service not known"
        )

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def reset(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("reset", request=request)

    def status(code: int) -> Handler:
        return lambda request: httpx.Response(code, text="echo " + request.headers["authorization"])

    cases = [
        (dns, "ai.network_dns"),
        (refused, "ai.network_connect"),
        (slow, "ai.timeout"),
        (reset, "ai.network"),
        (status(401), "ai.http_auth"),
        (status(404), "ai.http_not_found"),
        (status(429), "ai.http_rate_limit"),
        (status(503), "ai.http_server"),
        (status(400), "ai.http_rejected"),
    ]
    for handler, expected in cases:
        err = _failure(handler)
        assert err.code == expected
        assert KEY not in str(err)
        assert KEY not in repr(err)
    assert isinstance(_failure(slow), AiTimeoutError)
