"""Lectura de estimaciones del empleado (historial y detalle)."""

from typing import Any
from uuid import UUID

from supabase import Client

from app.models.agent import AgentRunTrace
from app.models.estimation import EstimationDetail, EstimationSummary
from app.models.project import Project
from app.models.report import ReportFile
from app.services.projects import get_project


class EstimationNotFoundError(Exception):
    def __init__(self, estimation_id: UUID) -> None:
        self.estimation_id = estimation_id
        super().__init__(f"No existe la estimación {estimation_id}.")


def _nested(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value:
        first = value[0]
        return first if isinstance(first, dict) else {}
    if isinstance(value, dict):
        return value
    return {}


def _summary(row: dict[str, Any]) -> EstimationSummary:
    project = _nested(row.get("projects"))
    name = project.get("name") if isinstance(project.get("name"), str) else ""
    return EstimationSummary(
        id=row["id"],
        problem_text=row["problem_text"],
        project_id=row["project_id"],
        project_name=name or "Proyecto",
        requested_by=row["requested_by"],
        created_at=row["created_at"],
    )


def list_estimations(client: Client, created_by: UUID) -> list[EstimationSummary]:
    """Estimaciones de todos los proyectos del empleado, más reciente primero."""
    projects = (
        client.table("projects")
        .select("id")
        .eq("created_by", str(created_by))
        .execute()
    )
    ids = [str(item["id"]) for item in (projects.data or []) if item.get("id")]
    if not ids:
        return []
    result = (
        client.table("estimations")
        .select(
            "id, problem_text, project_id, requested_by, created_at, projects(name)"
        )
        .in_("project_id", ids)
        .order("created_at", desc=True)
        .execute()
    )
    return [_summary(item) for item in (result.data or [])]


def list_project_estimations(
    client: Client, project_id: UUID, created_by: UUID
) -> list[EstimationSummary]:
    get_project(client, project_id, created_by)
    result = (
        client.table("estimations")
        .select(
            "id, problem_text, project_id, requested_by, created_at, projects(name)"
        )
        .eq("project_id", str(project_id))
        .order("created_at", desc=True)
        .execute()
    )
    return [_summary(item) for item in (result.data or [])]


def get_estimation(
    client: Client, estimation_id: UUID, created_by: UUID
) -> EstimationDetail:
    result = (
        client.table("estimations")
        .select(
            "id, problem_text, result_json, project_id, requested_by, created_at, "
            "projects(*)"
        )
        .eq("id", str(estimation_id))
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        raise EstimationNotFoundError(estimation_id)
    row = rows[0]
    project_row = _nested(row.get("projects"))
    if str(project_row.get("created_by")) != str(created_by) and str(
        row.get("requested_by")
    ) != str(created_by):
        raise EstimationNotFoundError(estimation_id)

    reports_result = (
        client.table("reports")
        .select("id, file_url, file_type, generated_at")
        .eq("estimation_id", str(estimation_id))
        .order("generated_at", desc=True)
        .execute()
    )
    reports = [
        ReportFile.model_validate(item) for item in (reports_result.data or [])
    ]

    raw_trace = row.get("result_json")
    trace = AgentRunTrace.model_validate(raw_trace) if raw_trace else None
    return EstimationDetail(
        id=row["id"],
        problem_text=row["problem_text"],
        result_json=trace,
        project_id=row["project_id"],
        project=Project.model_validate(project_row),
        requested_by=row["requested_by"],
        created_at=row["created_at"],
        reports=reports,
    )
