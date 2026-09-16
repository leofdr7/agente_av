from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}


@pytest.fixture
def supabase() -> MagicMock:
    client = MagicMock()
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


def auth_header(**kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {sign_token(PRIVATE_KEY, **kwargs)}"}


def test_me_without_token_returns_401(supabase) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    supabase.table.assert_not_called()


def test_me_with_invalid_token_returns_401(supabase) -> None:
    response = client.get(
        "/api/v1/me", headers={"Authorization": "Bearer definitely.not.valid"}
    )

    assert response.status_code == 401
    supabase.table.assert_not_called()


def test_me_with_expired_token_returns_401(supabase) -> None:
    response = client.get("/api/v1/me", headers=auth_header(expires_in=-60))

    assert response.status_code == 401
    assert response.json()["detail"] == "Token expirado."


def test_me_returns_existing_employee(supabase) -> None:
    select = supabase.table.return_value.select.return_value.eq.return_value.limit.return_value
    select.execute.return_value = MagicMock(data=[ROW])

    response = client.get("/api/v1/me", headers=auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["clerk_user_id"] == "user_123"
    assert body["name"] == "Ada Lovelace"
    supabase.table.return_value.insert.assert_not_called()


def test_me_creates_employee_on_first_access(supabase) -> None:
    select = supabase.table.return_value.select.return_value.eq.return_value.limit.return_value
    select.execute.return_value = MagicMock(data=[])
    supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[ROW]
    )

    response = client.get("/api/v1/me", headers=auth_header())

    assert response.status_code == 200
    supabase.table.return_value.insert.assert_called_once()


def test_me_without_profile_claims_returns_403(supabase) -> None:
    select = supabase.table.return_value.select.return_value.eq.return_value.limit.return_value
    select.execute.return_value = MagicMock(data=[])

    response = client.get("/api/v1/me", headers=auth_header(name=None, role=None))

    assert response.status_code == 403
    assert "name, role" in response.json()["detail"]
    supabase.table.return_value.insert.assert_not_called()


def test_health_stays_public() -> None:
    with patch("app.api.health.verify_supabase_connection", return_value={"connected": True}):
        response = client.get("/health")

    assert response.status_code == 200
