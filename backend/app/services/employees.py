"""Sincronización lazy de empleados: crea la fila en `employees` en el primer acceso."""

from postgrest.exceptions import APIError
from supabase import Client

from app.models.employee import ClerkClaims, Employee

UNIQUE_VIOLATION = "23505"


class IncompleteProfileError(Exception):
    """El token es válido pero no trae los claims necesarios para dar de alta al empleado."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            "El token no incluye los claims requeridos para crear el empleado: "
            + ", ".join(missing)
        )


def find_employee(client: Client, clerk_user_id: str) -> Employee | None:
    result = (
        client.table("employees")
        .select("*")
        .eq("clerk_user_id", clerk_user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return Employee.model_validate(result.data[0])


def get_or_create_employee(client: Client, claims: ClerkClaims) -> Employee:
    """Devuelve el empleado asociado al token; lo crea si es su primer acceso.

    Idempotente: si dos requests iniciales compiten, la restricción
    `employees.clerk_user_id UNIQUE` hace fallar al segundo INSERT y se
    devuelve la fila ya existente. El perfil no se sobrescribe en accesos
    posteriores.
    """
    existing = find_employee(client, claims.clerk_user_id)
    if existing is not None:
        return existing

    missing = [field for field in ("name", "role") if getattr(claims, field) is None]
    if missing:
        raise IncompleteProfileError(missing)

    try:
        result = (
            client.table("employees")
            .insert(
                {
                    "clerk_user_id": claims.clerk_user_id,
                    "name": claims.name,
                    "role": claims.role,
                }
            )
            .execute()
        )
    except APIError as exc:
        if exc.code != UNIQUE_VIOLATION:
            raise
        # Otro request creó el empleado entre el SELECT y el INSERT.
        concurrent = find_employee(client, claims.clerk_user_id)
        if concurrent is None:
            raise
        return concurrent

    return Employee.model_validate(result.data[0])
