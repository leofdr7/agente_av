"""Verificación de session tokens de Clerk contra su JWKS."""

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.models.employee import ClerkClaims

ALGORITHMS = ["RS256"]
# Tolerancia para desfase de reloj entre Clerk y este servidor.
LEEWAY_SECONDS = 10
# Los tokens de sesión de Clerk duran 60 s; la caché de claves puede ser mucho mayor.
JWKS_CACHE_LIFESPAN_SECONDS = 3600


class InvalidTokenError(Exception):
    """El token no pudo verificarse. `detail` es apto para devolverse al cliente."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@lru_cache
def get_jwks_client() -> PyJWKClient:
    return PyJWKClient(
        settings.clerk_jwks_url,
        cache_keys=True,
        lifespan=JWKS_CACHE_LIFESPAN_SECONDS,
    )


def verify_clerk_token(token: str) -> ClerkClaims:
    """Valida firma, expiración, emisor y `azp`; devuelve los claims tipados."""
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
    except jwt.PyJWKClientError as exc:
        raise InvalidTokenError("No se pudo obtener la clave de firma del token.") from exc
    except jwt.DecodeError as exc:
        raise InvalidTokenError("Token malformado.") from exc

    try:
        payload = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=ALGORITHMS,
            issuer=settings.clerk_issuer,
            leeway=LEEWAY_SECONDS,
            options={
                "require": ["exp", "iat", "sub", "iss"],
                "verify_aud": False,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token expirado.") from exc
    except jwt.InvalidIssuerError as exc:
        raise InvalidTokenError("Emisor del token no reconocido.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Token inválido.") from exc

    azp = payload.get("azp")
    if azp is not None and azp.rstrip("/") not in settings.authorized_parties:
        raise InvalidTokenError("Origen del token no autorizado.")

    return ClerkClaims.model_validate(payload)
