from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_key)


def verify_supabase_connection() -> dict[str, Any]:
    try:
        client = get_supabase_client()
        client.table("employees").select("id", count="exact").limit(0).execute()
        return {"connected": True}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
