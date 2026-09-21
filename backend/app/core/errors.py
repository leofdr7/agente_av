"""Respuestas de error homogéneas: JSON claro y sin stack traces en producción."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)

GENERIC_INTERNAL = "No se pudo completar la operación."
RATE_LIMIT_MESSAGE = (
    "Has alcanzado el límite de estimaciones de esta hora. "
    "Espera antes de lanzar otra para no disparar costos de la API."
)

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}


def error_body(*, code: str, message: str, detail: Any = None) -> dict[str, Any]:
    """Sobre común: `error` (código), `message` (texto legible) y `detail` (compat)."""
    return {
        "error": code,
        "message": message,
        "detail": message if detail is None else detail,
    }


def _status_code_name(status_code: int) -> str:
    return _STATUS_CODES.get(status_code, "http_error")


def detail_message(detail: Any, fallback: str = GENERIC_INTERNAL) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict) and item.get("msg"):
                parts.append(str(item["msg"]))
            elif isinstance(item, str) and item.strip():
                parts.append(item)
        if parts:
            return " ".join(parts)
    return fallback


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            code=_status_code_name(exc.status_code),
            message=detail_message(exc.detail),
            detail=exc.detail,
        ),
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body(
            code="validation_error",
            message="La petición no es válida.",
            detail=jsonable_encoder(exc.errors(), custom_encoder={Exception: str}),
        ),
    )


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error_body(
            code="rate_limited",
            message=RATE_LIMIT_MESSAGE,
            detail=RATE_LIMIT_MESSAGE,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Un handler genérico no debe tragar los tipos que ya tienen respuesta propia.
    if isinstance(exc, HTTPException) or isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await validation_exception_handler(request, exc)
    if isinstance(exc, RateLimitExceeded):
        return await rate_limit_handler(request, exc)

    logger.exception(
        "Excepción no controlada en %s %s", request.method, request.url.path
    )
    if settings.debug:
        message = f"{type(exc).__name__}: {exc}"
    else:
        message = GENERIC_INTERNAL
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(code="internal_error", message=message),
    )


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Capa extra: FastAPI no siempre despacha `Exception` desde las path operations."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        try:
            return await call_next(request)
        except Exception as exc:
            return await unhandled_exception_handler(request, exc)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(UnhandledErrorMiddleware)
