"""Endpoint del agente: autenticación Clerk y delegación en `run_agent`."""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from app.models.agent import AgentRunResponse, AgentRunTrace
from app.services.agent import MissingAnthropicKeyError
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
ANALISIS = "Plan de produccion inalcanzable por restriccion de materias primas."

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


def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {sign_token(PRIVATE_KEY)}"}


def body(**overrides) -> dict:
    payload = {
        "problem_text": "Nos quedamos cortos de resina, ¿qué plan es viable?",
        "project_id": str(uuid4()),
        "A": techchip.A,
        "B": techchip.DATASET_B,
        "variable_names": techchip.VARIABLE_NAMES,
        "resource_names": techchip.RESOURCE_NAMES,
    }
    payload.update(overrides)
    return payload


def test_run_requires_authentication() -> None:
    assert client.post(RUN_URL, json=body()).status_code == 401


@patch("app.api.agent.run_agent")
def test_run_delegates_to_agent_and_returns_analysis(
    mock_run_agent: MagicMock, supabase
) -> None:
    mock_run_agent.return_value = AgentRunResponse(
        estimation_id=ESTIMATION_ID,
        final_response=ANALISIS,
        result_json=AgentRunTrace(final_response=ANALISIS, model="claude-sonnet-5"),
    )

    response = client.post(RUN_URL, json=body(), headers=auth_header())

    assert response.status_code == 200
    payload = response.json()
    assert payload["estimation_id"] == str(ESTIMATION_ID)
    assert payload["final_response"] == ANALISIS
    assert payload["result_json"]["model"] == "claude-sonnet-5"

    request, requested_by = mock_run_agent.call_args.args
    assert request.problem_text == "Nos quedamos cortos de resina, ¿qué plan es viable?"
    assert requested_by == UUID(EMPLOYEE_ROW["id"])
    assert mock_run_agent.call_args.kwargs["supabase"] is supabase


@patch("app.api.agent.run_agent")
def test_run_without_anthropic_key_is_unavailable(
    mock_run_agent: MagicMock, supabase
) -> None:
    mock_run_agent.side_effect = MissingAnthropicKeyError("falta ANTHROPIC_API_KEY")

    response = client.post(RUN_URL, json=body(), headers=auth_header())

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_run_rejects_half_a_system(supabase) -> None:
    response = client.post(RUN_URL, json=body(B=None), headers=auth_header())

    assert response.status_code == 422
