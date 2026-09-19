from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.api.deps import CurrentEmployee
from app.db.supabase import get_supabase_client
from app.models.estimation import EstimationDetail, EstimationSummary
from app.models.report import ReportGenerationResponse
from app.services.estimations import (
    EstimationNotFoundError as EstimationLookupError,
)
from app.services.estimations import get_estimation, list_estimations
from app.services.report_generator import (
    EstimationIncompleteError,
    EstimationNotFoundError,
    ReportError,
    StorageUploadError,
    WeasyPrintUnavailableError,
    generate_reports,
)

router = APIRouter(prefix="/estimations", tags=["estimations"])


@router.get("", response_model=list[EstimationSummary])
def read_estimations(
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> list[EstimationSummary]:
    return list_estimations(supabase, employee.id)


@router.get("/{estimation_id}", response_model=EstimationDetail)
def read_estimation(
    estimation_id: UUID,
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> EstimationDetail:
    try:
        return get_estimation(supabase, estimation_id, employee.id)
    except EstimationLookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/{estimation_id}/report", response_model=ReportGenerationResponse)
def create_report(
    estimation_id: UUID,
    _employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> ReportGenerationResponse:
    """Genera el DOCX y el PDF de una estimación y devuelve URLs firmadas de descarga."""
    try:
        return generate_reports(estimation_id, supabase)
    except EstimationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except EstimationIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except WeasyPrintUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except StorageUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
