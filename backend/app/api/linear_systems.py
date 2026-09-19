from fastapi import APIRouter, HTTPException, status

from app.models.linear_system import LinearSystemInput, LinearSystemResult
from app.services.linear_systems_engine import (
    MethodInconsistencyError,
    solve_linear_system,
)

router = APIRouter(prefix="/linear-systems", tags=["linear-systems"])


@router.post("/solve", response_model=LinearSystemResult)
def solve(system: LinearSystemInput) -> LinearSystemResult:
    """Resuelve AX=B por Gauss, Gauss-Jordan y matriz inversa.

    Un sistema singular no es un error del cliente: se responde 200 con el
    diagnóstico (`solved: false`, `solution: null`) para que el consumidor lo
    presente como alerta.
    """
    try:
        return solve_linear_system(system)
    except MethodInconsistencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
