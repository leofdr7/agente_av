"""Entrada, traza y respuesta de una corrida del agente orquestador."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.linear_system import (
    CrossValidationReport,
    InfeasibilityFlag,
    LinearSystemInput,
    SubstitutionCheck,
)


class AgentRunRequest(BaseModel):
    """Problema planteado al agente: lenguaje natural y, opcionalmente, A y B directos."""

    problem_text: str = Field(min_length=1)
    project_id: UUID
    A: list[list[float]] | None = None
    B: list[float] | None = None
    # Etiquetas de negocio: columnas de A (líneas de producto) y filas de A (recursos).
    variable_names: list[str] | None = None
    resource_names: list[str] | None = None

    @model_validator(mode="after")
    def _check_system(self) -> "AgentRunRequest":
        if (self.A is None) != (self.B is None):
            raise ValueError(
                "A y B deben entregarse juntos: con uno solo no hay sistema que resolver. "
                "Omite ambos para que el agente los extraiga del enunciado."
            )
        if self.A is not None and self.B is not None:
            # Valida dimensiones y finitud con las mismas reglas que el motor.
            LinearSystemInput(A=self.A, B=self.B)
        return self


class ToolCallRecord(BaseModel):
    """Una llamada a herramienta ejecutada por el orquestador y su resultado."""

    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    is_error: bool = False


class AgentRunTrace(BaseModel):
    """Rastro completo de la corrida; se guarda tal cual en `estimations.result_json`."""

    A: list[list[float]] | None = None
    B: list[float] | None = None
    variable_names: list[str] | None = None
    resource_names: list[str] | None = None
    tools: list[ToolCallRecord] = Field(default_factory=list)
    cross_validation: CrossValidationReport | None = None
    substitution: SubstitutionCheck | None = None
    feasibility: InfeasibilityFlag | None = None
    final_response: str = ""
    model: str


class AgentRunResponse(BaseModel):
    """Respuesta del agente ya persistida en `estimations`."""

    estimation_id: UUID
    final_response: str
    result_json: AgentRunTrace
