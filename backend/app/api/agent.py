from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.api.deps import CurrentEmployee
from app.db.supabase import get_supabase_client
from app.models.agent import AgentRunRequest, AgentRunResponse
from app.services.agent import AgentError, MissingAnthropicKeyError, run_agent

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run", response_model=AgentRunResponse)
def run(
    request: AgentRunRequest,
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> AgentRunResponse:
    """Orquesta el análisis con Claude y lo registra en `estimations`.

    Un sistema singular o un plan infactible no son errores: el agente los devuelve
    explicados en lenguaje de negocio dentro de `final_response`.
    """
    try:
        return run_agent(request, employee.id, supabase=supabase)
    except MissingAnthropicKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except AgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
