"""Endpoint de informes: autenticación Clerk y delegación en `generate_reports`."""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from app.models.report import ReportFile, ReportGenerationResponse
from app.services.report_generator import (
    EstimationIncompleteError,
    EstimationNotFoundError,
)
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

EMPLOYEE_ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}
ESTIMATION_ID = UUID("9c5f1b2a-1111-4c3d-9d5a-1c2b3a4d5e6f")
REPORT_URL = f"/api/v1/estimations/{ESTIMATION_ID}/report"

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


def test_report_requires_authentication() -> None:
    assert client.post(REPORT_URL).status_code == 401


@patch("app.api.estimations.generate_reports")
def test_report_returns_signed_download_urls(
    mock_generate: MagicMock, supabase
) -> None:
    generated = "2026-09-19T04:00:00+00:00"
    mock_generate.return_value = ReportGenerationResponse(
        estimation_id=ESTIMATION_ID,
        reports=[
            ReportFile(
                id=uuid4(),
                file_url="https://signed.example/informe.docx",
                file_type="docx",
                generated_at=generated,
            ),
            ReportFile(
                id=uuid4(),
                file_url="https://signed.example/informe.pdf",
                file_type="pdf",
                generated_at=generated,
            ),
        ],
    )

    response = client.post(REPORT_URL, headers=auth_header())

    assert response.status_code == 200
    payload = response.json()
    assert payload["estimation_id"] == str(ESTIMATION_ID)
    types = {item["file_type"] for item in payload["reports"]}
    assert types == {"docx", "pdf"}
    assert all(item["file_url"].startswith("https://signed.example/") for item in payload["reports"])
    mock_generate.assert_called_once()
    assert mock_generate.call_args.args[0] == ESTIMATION_ID
    assert mock_generate.call_args.args[1] is supabase


@patch("app.api.estimations.generate_reports")
def test_report_missing_estimation_is_not_found(
    mock_generate: MagicMock, supabase
) -> None:
    mock_generate.side_effect = EstimationNotFoundError("No existe la estimación")
    response = client.post(REPORT_URL, headers=auth_header())
    assert response.status_code == 404


@patch("app.api.estimations.generate_reports")
def test_report_without_result_is_conflict(
    mock_generate: MagicMock, supabase
) -> None:
    mock_generate.side_effect = EstimationIncompleteError("aún no tiene resultado")
    response = client.post(REPORT_URL, headers=auth_header())
    assert response.status_code == 409
