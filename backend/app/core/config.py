from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JWKS_SUFFIX = "/.well-known/jwks.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Agente Algebra Vectorial"
    debug: bool = False
    supabase_url: str
    supabase_service_key: str

    # Clerk: URL del JWKS de la instancia (Frontend API + /.well-known/jwks.json).
    clerk_jwks_url: str
    # Emisor esperado en el claim `iss`. Si se omite, se deriva de CLERK_JWKS_URL.
    clerk_issuer: str | None = None
    # Orígenes del frontend autorizados a emitir tokens (claim `azp`), separados por coma.
    clerk_authorized_parties: str = "http://localhost:3000"

    # RAG / embeddings. Indexación y búsqueda deben usar el mismo proveedor y modelo.
    # Dimensión fija en 512 para coincidir con knowledge_chunks.embedding.
    embedding_provider: Literal["voyage", "openai"] = "voyage"
    voyage_api_key: str | None = None
    openai_api_key: str | None = None
    embedding_model: str | None = None
    vault_path: str | None = None

    @field_validator(
        "voyage_api_key",
        "openai_api_key",
        "embedding_model",
        "vault_path",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _derive_clerk_issuer(self) -> "Settings":
        if self.clerk_issuer is None:
            if not self.clerk_jwks_url.endswith(JWKS_SUFFIX):
                raise ValueError(
                    "CLERK_ISSUER es obligatorio cuando CLERK_JWKS_URL no termina en "
                    f"'{JWKS_SUFFIX}'."
                )
            self.clerk_issuer = self.clerk_jwks_url.removesuffix(JWKS_SUFFIX)
        self.clerk_issuer = self.clerk_issuer.rstrip("/")
        return self

    @property
    def authorized_parties(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.clerk_authorized_parties.split(",")
            if origin.strip()
        ]


settings = Settings()
