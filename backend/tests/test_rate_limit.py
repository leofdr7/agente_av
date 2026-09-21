"""Tope de estimaciones por empleado (slowapi)."""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter, reset_rate_limiter
from app.db.supabase import get_supabase_client
from app.main import app
from app.models.agent import AgentRunResponse, AgentRunTrace
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token
from tests.fixtures import techchip

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

EMPLOYEE_ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}
ESTIMATION_ID = UUID("9c5f1b2a-1111-4c3d-9d5a-1c2b3a4d5e6f")
RUN_URL = "/api/v1/agent/run"

client = TestClient(app)


@pytest.fixture
def supabase() -> MagicMock:
    supabase_client = MagicMock()
    select = (
        supabase_client.table.return_value.select.return_value.eq.return_value.limit.return_value
    )
    select.execute.return_value = MagicMock(data=[EMPLOYEE_ROW])
    app.dependency_overrides[get_supabase_client] = lambda: supabase_client
    yield supabase_client
    app.dependency_overrides.pop(get_supabase_client, None)


@pytest.fixture(autouse=True)
def fake_jwks():
    with patch(
        "app.core.security.get_jwks_client", return_value=FakeJWKSClient(PUBLIC_KEY)
    ):
        yield


@pytest.fixture(autouse=True)
def enable_limit():
    previous = limiter.enabled
    limiter.enabled = True
    reset_rate_limiter()
    yield
    reset_rate_limiter()
    limiter.enabled = previous


def auth_header(sub: str = "user_123") -> dict[str, str]:
    return {"Authorization": f"Bearer {sign_token(PRIVATE_KEY, sub=sub)}"}


def body() -> dict:
    return {
        "problem_text": "¿Qué plan cabe este turno?",
        "project_id": str(uuid4()),
        "A": techchip.A,
        "B": techchip.DATASET_B,
    }


@patch("app.api.agent.run_agent")
def test_tercer_run_en_la_hora_devuelve_429(mock_run: MagicMock, supabase) -> None:
    mock_run.return_value = AgentRunResponse(
        estimation_id=ESTIMATION_ID,
        final_response="ok",
        result_json=AgentRunTrace(final_response="ok", model="claude-sonnet-5"),
    )

    first = client.post(RUN_URL, json=body(), headers=auth_header())
    second = client.post(RUN_URL, json=body(), headers=auth_header())
    third = client.post(RUN_URL, json=body(), headers=auth_header())

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    payload = third.json()
    assert payload["error"] == "rate_limited"
    assert "límite de estimaciones" in payload["message"]
    assert mock_run.call_count == 2


@patch("app.api.agent.run_agent")
def test_otro_empleado_tiene_cupo_propio(mock_run: MagicMock, supabase) -> None:
    mock_run.return_value = AgentRunResponse(
        estimation_id=ESTIMATION_ID,
        final_response="ok",
        result_json=AgentRunTrace(final_response="ok", model="claude-sonnet-5"),
    )

    assert client.post(RUN_URL, json=body(), headers=auth_header("user_a")).status_code == 200
    assert client.post(RUN_URL, json=body(), headers=auth_header("user_a")).status_code == 200
    assert client.post(RUN_URL, json=body(), headers=auth_header("user_a")).status_code == 429
    assert client.post(RUN_URL, json=body(), headers=auth_header("user_b")).status_code == 200
