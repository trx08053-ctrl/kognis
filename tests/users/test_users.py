import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.users import EmailTakenError, InvalidCredentialsError, UserService
from kognis.users._domain import hash_token, normalize_email

VALID_PW = "correct horse"


def test_register_normalizes_email_and_authenticates(engine: Engine) -> None:
    with transaction(engine) as session:
        user = UserService(session).register("  Ann@Example.COM ", VALID_PW)
    assert user.email == "ann@example.com"
    with transaction(engine) as session:  # новое подключение: данные сохранились
        assert UserService(session).authenticate("ANN@example.com", VALID_PW) == user


def test_wrong_password_and_unknown_email_look_the_same(engine: Engine) -> None:
    with transaction(engine) as session:
        UserService(session).register("ann@example.com", VALID_PW)
    for email, password in [("ann@example.com", "wrong password"), ("bob@example.com", VALID_PW)]:
        with pytest.raises(InvalidCredentialsError) as info, transaction(engine) as session:
            UserService(session).authenticate(email, password)
        assert str(info.value) == "неверный email или пароль"


def test_duplicate_email_rejected(engine: Engine) -> None:
    with transaction(engine) as session:
        UserService(session).register("ann@example.com", VALID_PW)
    with pytest.raises(EmailTakenError), transaction(engine) as session:
        UserService(session).register("ANN@example.com", VALID_PW)


@pytest.mark.parametrize(
    ("email", "password", "message"),
    [
        ("no-at-sign", VALID_PW, "email"),
        ("a@b", VALID_PW, "email"),
        ("ann@example.com", "short", "пароль"),
    ],
)
def test_invalid_registration_rejected(
    engine: Engine, email: str, password: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message), transaction(engine) as session:
        UserService(session).register(email, password)


def test_session_lifecycle_and_token_not_stored_in_clear(engine: Engine) -> None:
    with transaction(engine) as session:
        service = UserService(session)
        user = service.register("ann@example.com", VALID_PW)
        token = service.start_session(user.id)
    with transaction(engine) as session:
        assert UserService(session).user_for_token(token) == user
        assert UserService(session).user_for_token("forged") is None
        UserService(session).end_session(token)
    with transaction(engine) as session:
        assert UserService(session).user_for_token(token) is None


@given(st.text(min_size=1, max_size=40))
def test_token_hash_is_not_the_token(token: str) -> None:
    digest = hash_token(token)
    assert digest != token
    assert len(digest) == 64


@given(st.emails())
def test_email_normalization_is_idempotent(email: str) -> None:
    once = normalize_email(email)
    assert normalize_email(once) == once
