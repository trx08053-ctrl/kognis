"""Коды и параметры ошибок доменных функций (kognis-b7x): точные значения, не только «упало»."""

import base64
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest

from kognis.analysis._domain import (
    MAX_ANSWER_LENGTH,
    MAX_ANSWERS,
    MAX_PERIOD_DAYS,
    direction_by_code,
    normalize_answers,
    validate_period,
)
from kognis.diary._domain import (
    ENVELOPE_IV_SIZE,
    ENVELOPE_KDF,
    ENVELOPE_MAX_SALT,
    ENVELOPE_MIN_CIPHER,
    ENVELOPE_MIN_ITERATIONS,
    ENVELOPE_MIN_SALT,
    ENVELOPE_VERSION,
    MAX_LABEL_LENGTH,
    MAX_LABELS,
    MAX_REFLECTION_LENGTH,
    MAX_TEXT_LENGTH,
    SCALE_MAX,
    SCALE_MIN,
    decode_cursor,
    normalize_labels,
    normalize_reflection,
    normalize_text,
    validate_envelope,
    validate_scale,
)
from kognis.errors import CodedValueError
from kognis.users._domain import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    LoginBlockedError,
    normalize_email,
    validate_locale,
    validate_password,
    validate_timezone,
)


def raised(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
    with pytest.raises(CodedValueError) as info:
        fn(*args, **kwargs)
    return info.value.code, info.value.params


def b64(size: int) -> str:
    return base64.b64encode(b"x" * size).decode()


def envelope(**over: Any) -> dict[str, Any]:
    good: dict[str, Any] = {
        "v": ENVELOPE_VERSION,
        "kdf": ENVELOPE_KDF,
        "iter": ENVELOPE_MIN_ITERATIONS,
        "salt": b64(ENVELOPE_MIN_SALT),
        "iv": b64(ENVELOPE_IV_SIZE),
        "ct": b64(ENVELOPE_MIN_CIPHER),
    }
    return {**good, **over}


def test_diary_scale_and_text_codes() -> None:
    assert raised(validate_scale, SCALE_MIN - 1, "mood") == (
        "diary.mood_range",
        {"min": SCALE_MIN, "max": SCALE_MAX},
    )
    assert raised(validate_scale, SCALE_MAX + 1, "wellbeing")[0] == "diary.wellbeing_range"
    assert validate_scale(SCALE_MIN, "mood") == SCALE_MIN
    assert validate_scale(SCALE_MAX, "mood") == SCALE_MAX
    assert raised(normalize_text, "  ") == ("diary.text_empty", {})
    assert raised(normalize_text, "a" * (MAX_TEXT_LENGTH + 1)) == (
        "diary.text_long",
        {"max": MAX_TEXT_LENGTH},
    )
    assert len(normalize_text("a" * MAX_TEXT_LENGTH)) == MAX_TEXT_LENGTH
    assert raised(normalize_reflection, "a" * (MAX_REFLECTION_LENGTH + 1)) == (
        "diary.reflection_long",
        {"max": MAX_REFLECTION_LENGTH},
    )
    assert len(normalize_reflection("a" * MAX_REFLECTION_LENGTH)) == MAX_REFLECTION_LENGTH


def test_diary_label_codes() -> None:
    for what in ("tags", "emotions"):
        assert raised(normalize_labels, ["a" * (MAX_LABEL_LENGTH + 1)], what) == (
            f"diary.{what}_item_long",
            {"max": MAX_LABEL_LENGTH},
        )
        many = [f"t{i}" for i in range(MAX_LABELS + 1)]
        assert raised(normalize_labels, many, what) == (f"diary.{what}_many", {"max": MAX_LABELS})
    assert len(normalize_labels([f"t{i}" for i in range(MAX_LABELS)], "tags")) == MAX_LABELS
    assert normalize_labels(["a" * MAX_LABEL_LENGTH], "tags") == ("a" * MAX_LABEL_LENGTH,)


@pytest.mark.parametrize(
    "bad",
    [
        {"v": ENVELOPE_VERSION + 1},
        {"kdf": "other"},
        {"iter": ENVELOPE_MIN_ITERATIONS - 1},
        {"iter": True},
        {"salt": 5},
        {"salt": "***"},
        {"salt": b64(ENVELOPE_MIN_SALT - 1)},
        {"salt": b64(ENVELOPE_MAX_SALT + 1)},
        {"iv": b64(ENVELOPE_IV_SIZE + 1)},
        {"ct": b64(ENVELOPE_MIN_CIPHER - 1)},
        {"ct": "A" * (4 * MAX_TEXT_LENGTH * 2 + 4)},
    ],
)
def test_envelope_invalid_code(bad: dict[str, Any]) -> None:
    assert raised(validate_envelope, envelope(**bad)) == ("diary.envelope_invalid", {})


def test_envelope_valid_passes() -> None:
    good = envelope()
    assert validate_envelope(good) == good


@pytest.mark.parametrize("raw", ["x", "2026-01-01", "2026-01-01.x", "2026-01-01."])
def test_cursor_invalid_code(raw: str) -> None:
    assert raised(decode_cursor, raw, with_id=True) == ("diary.cursor_invalid", {})
    assert decode_cursor("2026-01-01", with_id=False) == (date(2026, 1, 1), 0)
    assert raised(decode_cursor, "2026-01-01.1", with_id=False)[0] == "diary.cursor_invalid"
    assert (
        raised(decode_cursor, f"2026-01-01.{2**62 + 1}", with_id=True)[0] == "diary.cursor_invalid"
    )
    assert decode_cursor("2026-01-01.7", with_id=True) == (date(2026, 1, 1), 7)


def test_analysis_codes() -> None:
    assert raised(direction_by_code, "nope") == ("analysis.direction_unknown", {})
    assert raised(validate_period, date(2026, 2, 1), date(2026, 1, 1)) == (
        "analysis.period_reversed",
        {},
    )
    start = date(2026, 1, 1)
    assert raised(validate_period, start, start + timedelta(days=MAX_PERIOD_DAYS)) == (
        "analysis.period_long",
        {"max": MAX_PERIOD_DAYS},
    )
    validate_period(
        start, start + timedelta(days=MAX_PERIOD_DAYS - 1)
    )  # ровно MAX_PERIOD_DAYS суток
    assert raised(normalize_answers, [" "]) == ("analysis.answers_empty", {})
    assert raised(normalize_answers, ["a"] * (MAX_ANSWERS + 1)) == ("analysis.answers_long", {})
    assert raised(normalize_answers, ["a" * (MAX_ANSWER_LENGTH + 1)]) == (
        "analysis.answers_long",
        {},
    )
    assert len(normalize_answers(["a"] * MAX_ANSWERS)) == MAX_ANSWERS
    assert normalize_answers(["a" * MAX_ANSWER_LENGTH])


def test_user_codes() -> None:
    assert raised(normalize_email, "nope") == ("user.email_invalid", {})
    assert raised(validate_password, "a" * (MIN_PASSWORD_LENGTH - 1)) == (
        "user.password_short",
        {"min": MIN_PASSWORD_LENGTH},
    )
    assert raised(validate_password, "a" * (MAX_PASSWORD_LENGTH + 1)) == (
        "user.password_long",
        {"max": MAX_PASSWORD_LENGTH},
    )
    validate_password("a" * MIN_PASSWORD_LENGTH)
    validate_password("a" * MAX_PASSWORD_LENGTH)
    assert raised(validate_timezone, "Mars/Base") == ("user.timezone_unknown", {})
    assert raised(validate_locale, "xx") == ("user.locale_unsupported", {})
    assert validate_locale("ru") == "ru"
    blocked = LoginBlockedError(42)
    assert (blocked.code, blocked.params) == ("user.login_blocked", {"retry_after": 42})
