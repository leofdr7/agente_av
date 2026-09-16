from typing import Any

from fastapi import APIRouter

from app.db.supabase import verify_supabase_connection

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, Any]:
    database = verify_supabase_connection()
    status = "ok" if database.get("connected") else "degraded"
    return {"status": status, "database": database}
