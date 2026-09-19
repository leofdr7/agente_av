"""Lecturas de estimaciones para el frontend: listado, detalle e informes."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.agent import AgentRunTrace
from app.models.project import Project
from app.models.report import ReportFile


class EstimationSummary(BaseModel):
    """Fila de historial: sin la traza completa del agente."""

    id: UUID
    problem_text: str
    project_id: UUID
    project_name: str
    requested_by: UUID
    created_at: datetime


class EstimationDetail(BaseModel):
    """Resultado persistido, con proyecto e informes ya generados."""

    id: UUID
    problem_text: str
    result_json: AgentRunTrace | None = None
    project_id: UUID
    project: Project
    requested_by: UUID
    created_at: datetime
    reports: list[ReportFile] = Field(default_factory=list)
