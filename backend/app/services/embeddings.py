"""Cliente de embeddings: Voyage (recomendado) u OpenAI, siempre en 512 dimensiones."""

from collections.abc import Sequence
from typing import Literal

from app.core.config import settings

EMBEDDING_DIM = 512
BATCH_SIZE = 64
DEFAULT_MODELS = {
    "voyage": "voyage-4-lite",
    "openai": "text-embedding-3-small",
}

InputType = Literal["document", "query"]


class EmbeddingError(Exception):
    """Fallo al generar embeddings o al validar su dimensión."""


class MissingEmbeddingKeyError(EmbeddingError):
    """Falta la API key del proveedor de embeddings configurado."""


def resolve_embedding_model() -> str:
    if settings.embedding_model:
        return settings.embedding_model
    return DEFAULT_MODELS[settings.embedding_provider]


def embed_texts(
    texts: Sequence[str],
    input_type: InputType = "document",
) -> list[list[float]]:
    """Genera embeddings de 512 dimensiones, en el mismo orden que `texts`."""
    if not texts:
        return []

    provider = settings.embedding_provider
    if provider == "voyage":
        vectors = _embed_voyage(list(texts), input_type)
    elif provider == "openai":
        vectors = _embed_openai(list(texts))
    else:
        raise EmbeddingError(f"Proveedor de embeddings no soportado: {provider}")

    _assert_dimensions(vectors)
    return vectors


def _embed_voyage(texts: list[str], input_type: InputType) -> list[list[float]]:
    import voyageai

    api_key = settings.voyage_api_key
    if not api_key:
        raise MissingEmbeddingKeyError(
            "VOYAGE_API_KEY es obligatorio cuando EMBEDDING_PROVIDER=voyage."
        )

    client = voyageai.Client(api_key=api_key)
    model = resolve_embedding_model()
    embeddings: list[list[float]] = []
    for batch in _batched(texts, BATCH_SIZE):
        result = client.embed(
            batch,
            model=model,
            input_type=input_type,
            output_dimension=EMBEDDING_DIM,
        )
        embeddings.extend(list(result.embeddings))
    return embeddings


def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    api_key = settings.openai_api_key
    if not api_key:
        raise MissingEmbeddingKeyError(
            "OPENAI_API_KEY es obligatorio cuando EMBEDDING_PROVIDER=openai."
        )

    client = OpenAI(api_key=api_key)
    model = resolve_embedding_model()
    embeddings: list[list[float]] = []
    for batch in _batched(texts, BATCH_SIZE):
        response = client.embeddings.create(
            model=model,
            input=batch,
            dimensions=EMBEDDING_DIM,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        embeddings.extend(list(item.embedding) for item in ordered)
    return embeddings


def _assert_dimensions(vectors: list[list[float]]) -> None:
    for index, vector in enumerate(vectors):
        if len(vector) != EMBEDDING_DIM:
            raise EmbeddingError(
                f"El embedding {index} tiene {len(vector)} dimensiones; "
                f"se esperaban {EMBEDDING_DIM}."
            )


def _batched(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
