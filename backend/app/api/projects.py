from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.api.deps import CurrentEmployee
from app.db.supabase import get_supabase_client
from app.models.estimation import EstimationSummary
from app.models.project import Project, ProjectCreate, ProjectUpdate
from app.services.estimations import list_project_estimations
from app.services.projects import (
    ProjectError,
    ProjectNotFoundError,
    create_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _not_found(exc: ProjectNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("", response_model=list[Project])
def read_projects(
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> list[Project]:
    return list_projects(supabase, employee.id)


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_owned_project(
    payload: ProjectCreate,
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> Project:
    try:
        return create_project(supabase, employee.id, payload)
    except ProjectError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router.get("/{project_id}", response_model=Project)
def read_project(
    project_id: UUID,
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> Project:
    try:
        return get_project(supabase, project_id, employee.id)
    except ProjectNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/{project_id}", response_model=Project)
def patch_project(
    project_id: UUID,
    payload: ProjectUpdate,
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> Project:
    try:
        return update_project(supabase, project_id, employee.id, payload)
    except ProjectNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{project_id}/estimations", response_model=list[EstimationSummary])
def read_project_estimations(
    project_id: UUID,
    employee: CurrentEmployee,
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> list[EstimationSummary]:
    try:
        return list_project_estimations(supabase, project_id, employee.id)
    except ProjectNotFoundError as exc:
        raise _not_found(exc) from exc
