from unittest.mock import MagicMock, patch

from app.db.supabase import verify_supabase_connection


@patch("app.db.supabase.get_supabase_client")
def test_verify_supabase_connection_ok(mock_get_client) -> None:
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = (
        MagicMock()
    )

    result = verify_supabase_connection()

    assert result == {"connected": True}
    mock_client.table.assert_called_once_with("employees")


@patch("app.db.supabase.get_supabase_client")
def test_verify_supabase_connection_error(mock_get_client) -> None:
    mock_get_client.side_effect = Exception("connection refused")

    result = verify_supabase_connection()

    assert result["connected"] is False
    assert "connection refused" in result["error"]
