"""Resultados de búsqueda sobre `knowledge_chunks`."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeHit(BaseModel):
    """Chunk recuperado por similitud cosine, con su metadata de Obsidian."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    similarity: float
