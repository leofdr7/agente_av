from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.supabase import verify_supabase_connection

router = APIRouter()


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Sonda de proceso: una caída de Supabase no debe reiniciar contenedores."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    """Validación de despliegue sin exponer errores internos de la base de datos."""
    connected = verify_supabase_connection().get("connected", False)
    return JSONResponse(
        status_code=200 if connected else 503,
        content={"status": "ok" if connected else "unavailable"},
    )


@router.get("/health")
def health_check() -> dict[str, Any]:
    database = verify_supabase_connection()
    status = "ok" if database.get("connected") else "degraded"
    return {"status": status, "database": database}
