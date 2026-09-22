import pytest
from pydantic import ValidationError

from app.core.config import Settings


def production_settings(**overrides):
    values = {
        "environment": "production", "debug": False, "auth_disabled": False,
        "supabase_url": "https://example.supabase.co",
        "supabase_service_key": "test-service-key",
        "clerk_jwks_url": "https://clerk.example.com/.well-known/jwks.json",
        "clerk_secret_key": "test-clerk-key", "clerk_issuer": "https://clerk.example.com",
        "clerk_authorized_parties": "https://app.example.com,https://app.vercel.app",
        "anthropic_api_key": "test-anthropic-key",
        "embedding_provider": "openai", "openai_api_key": "test-openai-key",
    }
    return Settings(_env_file=None, **(values | overrides))


def test_production_with_exact_origins_and_secrets():
    assert production_settings().authorized_parties == [
        "https://app.example.com", "https://app.vercel.app",
    ]


@pytest.mark.parametrize("overrides", [
    {"debug": True}, {"auth_disabled": True},
    {"supabase_url": "http://example.supabase.co"},
    {"clerk_jwks_url": "http://clerk.example.com/.well-known/jwks.json"},
    {"clerk_authorized_parties": ""},
    {"clerk_authorized_parties": "http://localhost:3000"},
    {"clerk_authorized_parties": "https://*.vercel.app"},
    {"clerk_authorized_parties": "https://app.example.com/path"},
    {"anthropic_api_key": ""}, {"supabase_service_key": ""},
    {"clerk_secret_key": None}, {"openai_api_key": ""},
    {"embedding_provider": "voyage", "voyage_api_key": None},
])
def test_production_fails_closed(overrides):
    with pytest.raises(ValidationError):
        production_settings(**overrides)


def test_voyage_uses_its_own_key():
    assert production_settings(
        embedding_provider="voyage", voyage_api_key="test-voyage-key", openai_api_key=None,
    ).embedding_provider == "voyage"
