"""Endpoints de proyectos: autenticación Clerk y filtrado por empleado."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from app.models.estimation import EstimationSummary
from app.models.project import Project
from app.services.projects import ProjectNotFoundError
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


def test_list_projects_requires_authentication() -> None:
    assert client.get("/api/v1/projects").status_code == 401


@patch("app.api.projects.list_projects")
def test_list_projects_returns_employee_rows(
    mock_list: MagicMock, supabase
) -> None:
    mock_list.return_value = [PROJECT]

    response = client.get("/api/v1/projects", headers=auth_header())

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Línea AI-Edge"
    assert body[0]["budget"] == 120000.0
    assert body[0]["status"] == "active"
    mock_list.assert_called_once()
    assert mock_list.call_args.args[1] == EMPLOYEE_ID


@patch("app.api.projects.create_project")
def test_create_project_returns_201(mock_create: MagicMock, supabase) -> None:
    mock_create.return_value = PROJECT

    response = client.post(
        "/api/v1/projects",
        headers=auth_header(),
        json={"name": "  Línea AI-Edge  ", "budget": 120000},
    )

    assert response.status_code == 201
    payload = mock_create.call_args.args[2]
    assert payload.name == "Línea AI-Edge"
    assert payload.status == "active"
    assert payload.budget == Decimal("120000")


@patch("app.api.projects.get_project")
def test_get_project_not_found(mock_get: MagicMock, supabase) -> None:
    mock_get.side_effect = ProjectNotFoundError(PROJECT_ID)
    response = client.get(f"/api/v1/projects/{PROJECT_ID}", headers=auth_header())
    assert response.status_code == 404


@patch("app.api.projects.update_project")
def test_patch_project_budget(mock_update: MagicMock, supabase) -> None:
    updated = PROJECT.model_copy(update={"budget": Decimal("99000.50")})
    mock_update.return_value = updated

    response = client.patch(
        f"/api/v1/projects/{PROJECT_ID}",
        headers=auth_header(),
        json={"budget": 99000.50},
    )

    assert response.status_code == 200
    assert response.json()["budget"] == 99000.5
    mock_update.assert_called_once()


@patch("app.api.projects.list_project_estimations")
def test_list_project_estimations(mock_list: MagicMock, supabase) -> None:
    mock_list.return_value = [
        EstimationSummary(
            id=UUID("9c5f1b2a-1111-4c3d-9d5a-1c2b3a4d5e6f"),
            problem_text="Falta resina de encapsulado.",
            project_id=PROJECT_ID,
            project_name="Línea AI-Edge",
            requested_by=EMPLOYEE_ID,
            created_at=NOW,
        )
    ]

    response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/estimations",
        headers=auth_header(),
    )

    assert response.status_code == 200
    assert response.json()[0]["project_name"] == "Línea AI-Edge"
    mock_list.assert_called_once()


def test_create_project_rejects_empty_name(supabase) -> None:
    response = client.post(
        "/api/v1/projects",
        headers=auth_header(),
        json={"name": "   "},
    )
    assert response.status_code == 422
