from unittest.mock import patch

import pytest

from app.core.security import InvalidTokenError, verify_clerk_token
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()
OTHER_PRIVATE_KEY, _ = generate_keypair()


@pytest.fixture(autouse=True)
def fake_jwks():
    with patch(
        "app.core.security.get_jwks_client", return_value=FakeJWKSClient(PUBLIC_KEY)
    ):
        yield


def test_valid_token_returns_claims() -> None:
    claims = verify_clerk_token(sign_token(PRIVATE_KEY, sub="user_abc"))

    assert claims.clerk_user_id == "user_abc"
    assert claims.name == "Ada Lovelace"
    assert claims.role == "estimator"


def test_token_without_azp_is_accepted() -> None:
    claims = verify_clerk_token(sign_token(PRIVATE_KEY, azp=None))

    assert claims.azp is None


def test_blank_profile_claims_become_none() -> None:
    claims = verify_clerk_token(sign_token(PRIVATE_KEY, name="  ", role=""))

    assert claims.name is None
    assert claims.role is None


@pytest.mark.parametrize(
    ("token_kwargs", "expected_detail"),
    [
        ({"expires_in": -120}, "Token expirado."),
        ({"issuer": "https://evil.example.com"}, "Emisor del token no reconocido."),
        ({"azp": "https://evil.example.com"}, "Origen del token no autorizado."),
        ({"drop": ("sub",)}, "Token inválido."),
        ({"drop": ("exp",)}, "Token inválido."),
    ],
)
def test_invalid_claims_are_rejected(token_kwargs, expected_detail) -> None:
    with pytest.raises(InvalidTokenError) as excinfo:
        verify_clerk_token(sign_token(PRIVATE_KEY, **token_kwargs))

    assert excinfo.value.detail == expected_detail


def test_wrong_signature_is_rejected() -> None:
    with pytest.raises(InvalidTokenError) as excinfo:
        verify_clerk_token(sign_token(OTHER_PRIVATE_KEY))

    assert excinfo.value.detail == "Token inválido."


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(InvalidTokenError) as excinfo:
        verify_clerk_token("not-a-jwt")

    assert excinfo.value.detail == "Token malformado."
