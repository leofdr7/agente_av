"""Utilidades para firmar tokens de prueba equivalentes a los de Clerk."""

import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://test.clerk.accounts.dev"
AUTHORIZED_PARTY = "http://localhost:3000"
KID = "test-kid"


@dataclass
class FakeSigningKey:
    key: Any


class FakeJWKSClient:
    """Sustituye a PyJWKClient devolviendo siempre la clave pública de prueba."""

    def __init__(self, public_key: Any) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        jwt.get_unverified_header(token)  # Falla con DecodeError si está malformado.
        return FakeSigningKey(key=self._public_key)


def generate_keypair() -> tuple[Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def private_key_pem(private_key: Any) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def sign_token(
    private_key: Any,
    *,
    sub: str = "user_123",
    name: str | None = "Ada Lovelace",
    role: str | None = "estimator",
    issuer: str = ISSUER,
    azp: str | None = AUTHORIZED_PARTY,
    expires_in: int = 60,
    extra: dict[str, Any] | None = None,
    drop: tuple[str, ...] = (),
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "iat": now,
        "nbf": now,
        "exp": now + expires_in,
        "sid": "sess_123",
    }
    if azp is not None:
        payload["azp"] = azp
    if name is not None:
        payload["name"] = name
    if role is not None:
        payload["role"] = role
    if extra:
        payload.update(extra)
    for claim in drop:
        payload.pop(claim, None)
    return jwt.encode(
        payload, private_key_pem(private_key), algorithm="RS256", headers={"kid": KID}
    )
