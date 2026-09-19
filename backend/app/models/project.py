"""Proyectos del empleado: presupuesto, estado y metadatos de alta."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator

ProjectStatus = Literal["draft", "active", "on_hold", "completed", "archived"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    budget: Decimal | None = Field(default=None, ge=0)
    status: ProjectStatus = "active"

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("El nombre no puede estar vacío.")
        return stripped


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    budget: Decimal | None = Field(default=None, ge=0)
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("El nombre no puede estar vacío.")
        return stripped

    def as_patch(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.name is not None:
            payload["name"] = self.name
        if self.budget is not None:
            payload["budget"] = str(self.budget)
        if self.status is not None:
            payload["status"] = self.status
        return payload


class Project(BaseModel):
    id: UUID
    name: str
    budget: Decimal | None = None
    status: ProjectStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    @field_serializer("budget")
    def _serialize_budget(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None
