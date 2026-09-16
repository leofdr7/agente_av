import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault(
    "CLERK_JWKS_URL", "https://test.clerk.accounts.dev/.well-known/jwks.json"
)
os.environ.setdefault("CLERK_AUTHORIZED_PARTIES", "http://localhost:3000")
