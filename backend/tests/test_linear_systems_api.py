from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token
from tests.fixtures import techchip

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}

SOLVE_URL = "/api/v1/linear-systems/solve"


@pytest.fixture
def supabase() -> MagicMock:
    client = MagicMock()
    select = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    select.execute.return_value = MagicMock(data=[ROW])
    app.dependency_overrides[get_supabase_client] = lambda: client
    yield client
    app.dependency_overrides.pop(get_supabase_client, None)


@pytest.fixture(autouse=True)
def fake_jwks():
    with patch(
        "app.core.security.get_jwks_client", return_value=FakeJWKSClient(PUBLIC_KEY)
    ):
        yield


client = TestClient(app)


def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {sign_token(PRIVATE_KEY)}"}


def test_solve_requires_authentication() -> None:
    response = client.post(SOLVE_URL, json={"A": techchip.A, "B": techchip.DATASET_B})

    assert response.status_code == 401


def test_solve_returns_expected_production_plan(supabase) -> None:
    response = client.post(
        SOLVE_URL,
        json={"A": techchip.A, "B": techchip.DATASET_B},
        headers=auth_header(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["solved"] is True
    assert body["solution"] == pytest.approx(techchip.X_ESPERADA, abs=1e-6)
    assert body["feasibility"]["infeasible"] is False


def test_solve_reports_singular_system_as_200_with_diagnosis(supabase) -> None:
    degenerate = [list(row) for row in techchip.A]
    degenerate[5] = [2 * value for value in techchip.A[0]]

    response = client.post(
        SOLVE_URL,
        json={"A": degenerate, "B": techchip.DATASET_B},
        headers=auth_header(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["solved"] is False
    assert body["solution"] is None
    assert body["diagnosis"]["classification"] == "incompatible"


def test_solve_rejects_mismatched_dimensions(supabase) -> None:
    response = client.post(
        SOLVE_URL, json={"A": [[1, 2], [3, 4]], "B": [1, 2, 3]}, headers=auth_header()
    )

    assert response.status_code == 422
