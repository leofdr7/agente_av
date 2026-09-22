import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AUTH_DISABLED", "false")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault(
    "CLERK_JWKS_URL", "https://test.clerk.accounts.dev/.well-known/jwks.json"
)
os.environ.setdefault("CLERK_AUTHORIZED_PARTIES", "http://localhost:3000")
# Los tests no deben chocar con el tope horario; el propio test de quota lo reactiva.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("ESTIMATION_RATE_LIMIT", "2/hour")
