from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.api.health.verify_supabase_connection")
def test_health_check_ok(mock_verify) -> None:
    mock_verify.return_value = {"connected": True}

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": {"connected": True},
    }


@patch("app.api.health.verify_supabase_connection")
def test_health_check_degraded(mock_verify) -> None:
    mock_verify.return_value = {"connected": False, "error": "timeout"}

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["connected"] is False
    assert body["database"]["error"] == "timeout"
