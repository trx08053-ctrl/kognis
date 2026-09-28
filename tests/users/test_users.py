import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.engine import Engine

from kognis.db import transaction
from kognis.users import UserService
from kognis.users._domain import normalize_name


def test_register_normalizes_name_and_persists(engine: Engine) -> None:
    with transaction(engine) as session:
        user = UserService(session).register("  Ann ")
    with transaction(engine) as session:
        assert UserService(session).get(user.id) == user
        assert user.name == "Ann"


def test_blank_name_rejected(engine: Engine) -> None:
    with pytest.raises(ValueError, match="пуст"), transaction(engine) as session:
        UserService(session).register("   ")


def test_list_in_registration_order(engine: Engine) -> None:
    with transaction(engine) as session:
        service = UserService(session)
        b, a = service.register("B"), service.register("A")
        assert service.list_all() == [b, a]


@given(st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1, max_size=50))
def test_normalized_name_is_stripped(name: str) -> None:
    assert normalize_name(f"  {name} ") == name
