from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JWKS_SUFFIX = "/.well-known/jwks.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True,
    )

    app_name: str = "Agente Algebra Vectorial"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    supabase_url: str
    supabase_service_key: str

    # Clerk: URL del JWKS de la instancia (Frontend API + /.well-known/jwks.json).
    clerk_jwks_url: str
    # Se almacena en Secret Manager; la verificación de JWT usa JWKS público.
    clerk_secret_key: str | None = None
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

    # Anthropic: orquestador del agente (tool use). El modelo nunca calcula AX=B.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    # Bypass de autenticacion SOLO para testing local. Nunca usar en produccion.
    auth_disabled: bool = False

    # Informes PDF/DOCX: bucket privado de Storage y caducidad de las URLs firmadas.
    reports_bucket: str = "reports"
    reports_signed_url_ttl_seconds: int = 604800

    # Rate limit de POST /api/v1/agent/run, por empleado (slowapi, ventana móvil).
    rate_limit_enabled: bool = True
    estimation_rate_limit: str = "10/hour"

    @field_validator(
        "voyage_api_key",
        "openai_api_key",
        "embedding_model",
        "vault_path",
        "anthropic_api_key",
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

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.debug or self.auth_disabled:
            raise ValueError("Producción requiere DEBUG=false y AUTH_DISABLED=false.")
        for name, value in {
            "SUPABASE_URL": self.supabase_url,
            "CLERK_JWKS_URL": self.clerk_jwks_url,
            "CLERK_ISSUER": self.clerk_issuer or "",
        }.items():
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError(f"{name} debe ser una URL HTTPS en producción.")
        if not self.authorized_parties:
            raise ValueError("CLERK_AUTHORIZED_PARTIES requiere al menos un origen.")
        for origin in self.authorized_parties:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https" or not parsed.hostname
                or "*" in origin or parsed.path or parsed.query or parsed.fragment
                or parsed.username or parsed.password
            ):
                raise ValueError("Los orígenes de producción deben ser orígenes HTTPS exactos.")
        keys = {
            "SUPABASE_SERVICE_KEY": self.supabase_service_key,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "CLERK_SECRET_KEY": self.clerk_secret_key,
            f"{self.embedding_provider.upper()}_API_KEY": (
                self.openai_api_key if self.embedding_provider == "openai" else self.voyage_api_key
            ),
        }
        for name, value in keys.items():
            if not value or not value.strip():
                raise ValueError(f"{name} es obligatorio en producción.")
        return self

    @property
    def authorized_parties(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.clerk_authorized_parties.split(",")
            if origin.strip()
        ]


settings = Settings()
