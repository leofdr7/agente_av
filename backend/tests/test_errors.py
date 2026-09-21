"""Handler global: JSON homogéneo y sin stack traces fuera de debug."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import GENERIC_INTERNAL
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


@patch("app.api.health.verify_supabase_connection")
def test_unhandled_exception_hides_internals_in_production(mock_verify, monkeypatch) -> None:
    mock_verify.side_effect = RuntimeError("secret internals of the solver")
    monkeypatch.setattr(settings, "debug", False)

    response = client.get("/health")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["message"] == GENERIC_INTERNAL
    assert body["detail"] == GENERIC_INTERNAL
    assert "secret internals" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


@patch("app.api.health.verify_supabase_connection")
def test_unhandled_exception_names_the_error_in_debug(mock_verify, monkeypatch) -> None:
    mock_verify.side_effect = RuntimeError("secret internals of the solver")
    monkeypatch.setattr(settings, "debug", True)

    response = client.get("/health")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert "RuntimeError" in body["message"]
    assert "secret internals" in body["message"]
    assert "Traceback" not in response.text


def test_http_error_keeps_detail_and_adds_message() -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "unauthorized"
    assert body["message"]
    assert body["detail"]
