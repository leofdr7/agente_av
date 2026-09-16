from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError

from app.models.employee import ClerkClaims
from app.services.employees import IncompleteProfileError, get_or_create_employee

ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}


def make_client(select_results: list[list[dict]], insert_side_effect=None) -> MagicMock:
    client = MagicMock()
    table = client.table.return_value

    select_chain = table.select.return_value.eq.return_value.limit.return_value
    select_chain.execute.side_effect = [MagicMock(data=rows) for rows in select_results]

    insert_execute = table.insert.return_value.execute
    if insert_side_effect is not None:
        insert_execute.side_effect = insert_side_effect
    else:
        insert_execute.return_value = MagicMock(data=[ROW])
    return client


def claims(**overrides) -> ClerkClaims:
    payload = {"sub": "user_123", "name": "Ada Lovelace", "role": "estimator"}
    payload.update(overrides)
    return ClerkClaims.model_validate(payload)


def test_returns_existing_employee_without_inserting() -> None:
    client = make_client([[ROW]])

    employee = get_or_create_employee(client, claims(name="Otro nombre", role="admin"))

    assert employee.clerk_user_id == "user_123"
    assert employee.name == "Ada Lovelace"  # No se sobrescribe el perfil.
    client.table.return_value.insert.assert_not_called()


def test_creates_employee_on_first_access() -> None:
    client = make_client([[]])

    employee = get_or_create_employee(client, claims())

    client.table.return_value.insert.assert_called_once_with(
        {"clerk_user_id": "user_123", "name": "Ada Lovelace", "role": "estimator"}
    )
    assert employee.role == "estimator"


@pytest.mark.parametrize(
    ("overrides", "missing"),
    [
        ({"name": None}, ["name"]),
        ({"role": None}, ["role"]),
        ({"name": None, "role": None}, ["name", "role"]),
    ],
)
def test_missing_profile_claims_block_creation(overrides, missing) -> None:
    client = make_client([[]])

    with pytest.raises(IncompleteProfileError) as excinfo:
        get_or_create_employee(client, claims(**overrides))

    assert excinfo.value.missing == missing
    client.table.return_value.insert.assert_not_called()


def test_concurrent_insert_falls_back_to_existing_row() -> None:
    duplicate = APIError(
        {"code": "23505", "message": "duplicate key", "details": None, "hint": None}
    )
    client = make_client([[], [ROW]], insert_side_effect=duplicate)

    employee = get_or_create_employee(client, claims())

    assert employee.clerk_user_id == "user_123"


def test_unexpected_database_error_propagates() -> None:
    failure = APIError(
        {"code": "42501", "message": "permission denied", "details": None, "hint": None}
    )
    client = make_client([[]], insert_side_effect=failure)

    with pytest.raises(APIError):
        get_or_create_employee(client, claims())
