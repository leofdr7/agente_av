from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.api.health.verify_supabase_connection", side_effect=AssertionError("No DB on liveness"))
def test_liveness_does_not_depend_on_database(mock_verify) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    mock_verify.assert_not_called()


@patch("app.api.health.verify_supabase_connection")
def test_readiness_returns_503_without_internal_details(mock_verify) -> None:
    mock_verify.return_value = {"connected": False, "error": "private database detail"}
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@patch("app.api.health.verify_supabase_connection", return_value={"connected": True})
def test_readiness_returns_200(mock_verify) -> None:
    assert client.get("/health/ready").status_code == 200


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
