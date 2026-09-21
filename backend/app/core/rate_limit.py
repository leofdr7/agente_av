"""Límite de estimaciones por empleado (slowapi) para contener el gasto de Anthropic."""

from __future__ import annotations

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def employee_rate_key(request: Request) -> str:
    """Clave por `sub` del JWT (un empleado); si no hay token, por IP."""
    header = request.headers.get("authorization") or ""
    token = header.split(" ", 1)[1] if header.lower().startswith("bearer ") else ""
    if token:
        try:
            claims = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
            )
            sub = claims.get("sub")
            if isinstance(sub, str) and sub.strip():
                return f"employee:{sub.strip()}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=employee_rate_key,
    enabled=settings.rate_limit_enabled,
    headers_enabled=False,
    default_limits=[],
)


def reset_rate_limiter() -> None:
    """Vacía el contador in-memory. Solo para tests."""
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "reset"):
        storage.reset()
        return
    inner = getattr(getattr(limiter, "limiter", None), "_storage", None)
    if inner is not None and hasattr(inner, "reset"):
        inner.reset()
        return
    nested = getattr(getattr(limiter, "_limiter", None), "storage", None)
    if nested is not None and hasattr(nested, "reset"):
        nested.reset()
