from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.api.deps import CurrentEmployee
from app.db.supabase import get_supabase_client
from app.models.knowledge import KnowledgeSearchResponse
from app.services.embeddings import EmbeddingError, MissingEmbeddingKeyError
from app.services.rag import search_knowledge

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/search", response_model=KnowledgeSearchResponse)
def search(
    _employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
    q: str = Query(..., min_length=1, description="Consulta en lenguaje natural"),
    top_k: int = Query(5, ge=1, le=20),
) -> KnowledgeSearchResponse:
    """Búsqueda RAG sobre los fragmentos indexados del vault."""
    try:
        hits = search_knowledge(q, top_k=top_k, client=supabase)
    except MissingEmbeddingKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return KnowledgeSearchResponse(query=q.strip(), results=hits)
