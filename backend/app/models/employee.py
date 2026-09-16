from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClerkClaims(BaseModel):
    """Claims relevantes del session token de Clerk ya verificado."""

    model_config = ConfigDict(extra="ignore")

    sub: str = Field(min_length=1)
    azp: str | None = None
    # Claims personalizados configurados en Clerk (ver README).
    name: str | None = None
    role: str | None = None

    @field_validator("name", "role", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @property
    def clerk_user_id(self) -> str:
        return self.sub


class Employee(BaseModel):
    id: UUID
    clerk_user_id: str
    name: str
    role: str
    created_at: datetime
