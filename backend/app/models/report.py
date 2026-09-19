"""Respuesta del endpoint de generación de informes."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ReportFile(BaseModel):
    """Una salida persistida en `reports` y en el bucket de Storage."""

    id: UUID
    file_url: str
    file_type: Literal["pdf", "docx"]
    generated_at: datetime


class ReportGenerationResponse(BaseModel):
    """URLs de descarga de los dos documentos generados para una estimación."""

    estimation_id: UUID
    reports: list[ReportFile]
