"""Búsqueda semántica sobre el vault indexado en `knowledge_chunks`."""

from supabase import Client

from app.db.supabase import get_supabase_client
from app.models.knowledge import KnowledgeHit
from app.services.embeddings import embed_texts


def search_knowledge(
    query: str,
    top_k: int = 5,
    *,
    client: Client | None = None,
) -> list[KnowledgeHit]:
    """Genera el embedding de `query` y devuelve los `top_k` chunks más similares."""
    cleaned = query.strip()
    if not cleaned:
        return []
    if top_k < 1:
        return []

    query_embedding = embed_texts([cleaned], input_type="query")[0]
    supabase = client or get_supabase_client()
    result = supabase.rpc(
        "match_knowledge_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": top_k,
        },
    ).execute()
    rows = result.data or []
    return [KnowledgeHit.model_validate(row) for row in rows]
