"""GET de estimaciones: listado, detalle y aislamiento por empleado."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from app.models.agent import AgentRunTrace
from app.models.estimation import EstimationDetail, EstimationSummary
from app.models.project import Project
from app.services.estimations import EstimationNotFoundError
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

EMPLOYEE_ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}
EMPLOYEE_ID = UUID(EMPLOYEE_ROW["id"])
PROJECT_ID = UUID("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa")
ESTIMATION_ID = UUID("9c5f1b2a-1111-4c3d-9d5a-1c2b3a4d5e6f")
NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)

PROJECT = Project(
    id=PROJECT_ID,
    name="Línea AI-Edge",
    budget=Decimal("120000.00"),
    status="active",
    created_by=EMPLOYEE_ID,
    created_at=NOW,
    updated_at=NOW,
)

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


def test_list_estimations_requires_authentication() -> None:
    assert client.get("/api/v1/estimations").status_code == 401


@patch("app.api.estimations.list_estimations")
def test_list_estimations(mock_list: MagicMock, supabase) -> None:
    mock_list.return_value = [
        EstimationSummary(
            id=ESTIMATION_ID,
            problem_text="Falta resina de encapsulado.",
            project_id=PROJECT_ID,
            project_name="Línea AI-Edge",
            requested_by=EMPLOYEE_ID,
            created_at=NOW,
        )
    ]

    response = client.get("/api/v1/estimations", headers=auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(ESTIMATION_ID)
    assert body[0]["project_name"] == "Línea AI-Edge"
    mock_list.assert_called_once()
    assert mock_list.call_args.args[1] == EMPLOYEE_ID


@patch("app.api.estimations.get_estimation")
def test_get_estimation_detail(mock_get: MagicMock, supabase) -> None:
    mock_get.return_value = EstimationDetail(
        id=ESTIMATION_ID,
        problem_text="Falta resina de encapsulado.",
        result_json=AgentRunTrace(
            final_response="Plan inalcanzable por restricción de resina.",
            model="claude-sonnet-5",
        ),
        project_id=PROJECT_ID,
        project=PROJECT,
        requested_by=EMPLOYEE_ID,
        created_at=NOW,
        reports=[],
    )

    response = client.get(
        f"/api/v1/estimations/{ESTIMATION_ID}", headers=auth_header()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result_json"]["final_response"].startswith("Plan inalcanzable")
    assert body["project"]["name"] == "Línea AI-Edge"


@patch("app.api.estimations.get_estimation")
def test_get_estimation_not_found(mock_get: MagicMock, supabase) -> None:
    mock_get.side_effect = EstimationNotFoundError(ESTIMATION_ID)
    response = client.get(
        f"/api/v1/estimations/{ESTIMATION_ID}", headers=auth_header()
    )
    assert response.status_code == 404
