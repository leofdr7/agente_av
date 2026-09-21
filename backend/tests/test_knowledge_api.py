"""GET /api/v1/knowledge/search: RAG autenticado con Supabase simulado."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

EMPLOYEE_ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}
SEARCH_URL = "/api/v1/knowledge/search"
CHUNK_ID = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"

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


def test_search_requires_authentication() -> None:
    assert client.get(SEARCH_URL, params={"q": "resina"}).status_code == 401


@patch("app.services.rag.embed_texts")
def test_search_returns_ranked_chunks(mock_embed: MagicMock, supabase) -> None:
    mock_embed.return_value = [[0.1] * 512]
    supabase.rpc.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": CHUNK_ID,
                "content": "La resina de encapsulado es el recurso más restrictivo.",
                "metadata": {"obsidian_path": "recursos.md", "title": "Recursos"},
                "similarity": 0.91,
            }
        ]
    )

    response = client.get(
        SEARCH_URL, params={"q": "resina de encapsulado", "top_k": 3}, headers=auth_header()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "resina de encapsulado"
    assert body["results"][0]["id"] == CHUNK_ID
    assert "resina de encapsulado" in body["results"][0]["content"]
    assert body["results"][0]["similarity"] == 0.91
    mock_embed.assert_called_once_with(["resina de encapsulado"], input_type="query")
    supabase.rpc.assert_called_once_with(
        "match_knowledge_chunks",
        {"query_embedding": mock_embed.return_value[0], "match_count": 3},
    )
    assert UUID(body["results"][0]["id"])
