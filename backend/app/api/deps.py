from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.core.security import InvalidTokenError, verify_clerk_token
from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.models.employee import ClerkClaims, Employee
from app.services.employees import IncompleteProfileError, get_or_create_employee

bearer_scheme = HTTPBearer(auto_error=False)
UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_token_claims(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> ClerkClaims:
    """Exige `Authorization: Bearer <session token de Clerk>` y devuelve sus claims."""
    if settings.auth_disabled:
        return ClerkClaims(sub="test-user-local", name="Test Local", role="admin")
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado Authorization con un Bearer token.",
            headers=UNAUTHORIZED_HEADERS,
        )
    try:
        return verify_clerk_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.detail,
            headers=UNAUTHORIZED_HEADERS,
        ) from exc


def get_current_employee(
    claims: Annotated[ClerkClaims, Depends(get_token_claims)],
    client: Annotated[Client, Depends(get_supabase_client)],
) -> Employee:
    """Resuelve el empleado autenticado, creándolo en su primer acceso."""
    try:
        return get_or_create_employee(client, claims)
    except IncompleteProfileError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


CurrentEmployee = Annotated[Employee, Depends(get_current_employee)]
