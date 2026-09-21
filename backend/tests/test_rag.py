from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from app.services.embeddings import embed_texts
from app.services.rag import DEFAULT_MIN_SIMILARITY, search_knowledge


def test_embed_texts_empty_returns_empty() -> None:
    assert embed_texts([]) == []


def test_search_knowledge_empty_query_skips_rpc() -> None:
    client = MagicMock()
    assert search_knowledge("   ", top_k=5, client=client) == []
    client.rpc.assert_not_called()


@patch("app.services.rag.embed_texts")
def test_search_knowledge_calls_match_rpc(mock_embed: MagicMock) -> None:
    mock_embed.return_value = [[0.25] * 512]
    client = MagicMock()
    client.rpc.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
                "content": "Parámetros de extrusión",
                "metadata": {"obsidian_path": "procesos/extrusion.md", "title": "Extrusión"},
                "similarity": 0.88,
            }
        ]
    )

    hits = search_knowledge("¿qué es extrusión?", top_k=3, client=client)

    mock_embed.assert_called_once_with(["¿qué es extrusión?"], input_type="query")
    client.rpc.assert_called_once_with(
        "match_knowledge_chunks",
        {"query_embedding": mock_embed.return_value[0], "match_count": 3},
    )
    assert len(hits) == 1
    assert hits[0].id == UUID("3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f")
    assert hits[0].metadata["obsidian_path"] == "procesos/extrusion.md"
    assert hits[0].similarity == 0.88


def chunk(content: str, similarity: float) -> dict:
    return {
        "id": str(uuid4()),
        "content": content,
        "metadata": {"obsidian_path": "procesos/extrusion.md", "title": "Extrusión"},
        "similarity": similarity,
    }


def rpc_client(*rows: dict) -> MagicMock:
    client = MagicMock()
    client.rpc.return_value.execute.return_value = MagicMock(data=list(rows))
    return client


@patch("app.services.rag.embed_texts")
def test_search_knowledge_descarta_los_chunks_poco_relevantes(mock_embed: MagicMock) -> None:
    mock_embed.return_value = [[0.25] * 512]
    client = rpc_client(chunk("Relevante", 0.71), chunk("Ruido", 0.18))

    hits = search_knowledge("¿qué es extrusión?", top_k=5, client=client)

    assert [hit.content for hit in hits] == ["Relevante"]


@patch("app.services.rag.embed_texts")
def test_search_knowledge_sin_chunks_sobre_el_umbral_devuelve_vacio(
    mock_embed: MagicMock,
) -> None:
    mock_embed.return_value = [[0.25] * 512]
    client = rpc_client(chunk("Ruido", 0.49), chunk("Más ruido", 0.02))

    assert search_knowledge("tema ajeno al vault", top_k=5, client=client) == []


@patch("app.services.rag.embed_texts")
def test_search_knowledge_conserva_la_similitud_igual_al_umbral(mock_embed: MagicMock) -> None:
    mock_embed.return_value = [[0.25] * 512]
    client = rpc_client(chunk("En el límite", DEFAULT_MIN_SIMILARITY))

    hits = search_knowledge("¿qué es extrusión?", top_k=5, client=client)

    assert [hit.content for hit in hits] == ["En el límite"]


@patch("app.services.rag.embed_texts")
def test_search_knowledge_respeta_un_min_similarity_explicito(mock_embed: MagicMock) -> None:
    mock_embed.return_value = [[0.25] * 512]
    client = rpc_client(chunk("Fuerte", 0.95), chunk("Media", 0.62))

    hits = search_knowledge("¿qué es extrusión?", top_k=5, client=client, min_similarity=0.9)

    assert [hit.content for hit in hits] == ["Fuerte"]
