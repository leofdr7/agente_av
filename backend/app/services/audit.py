"""Registro de auditoría de cada estimación: quién, cuándo, qué proyecto, qué tools."""

from uuid import UUID

from supabase import Client


class AuditLogError(Exception):
    """No se pudo persistir la fila en `audit_logs`."""


def summarize_tools(tool_names: list[str]) -> str:
    if not tool_names:
        return "No se invocó ninguna herramienta."
    return f"{len(tool_names)} llamada(s): " + " → ".join(tool_names)


def record_estimation_audit(
    client: Client,
    *,
    employee_id: UUID,
    project_id: UUID,
    estimation_id: UUID,
    tool_names: list[str],
) -> None:
    result = (
        client.table("audit_logs")
        .insert(
            {
                "employee_id": str(employee_id),
                "project_id": str(project_id),
                "estimation_id": str(estimation_id),
                "tools_used": tool_names,
                "tools_summary": summarize_tools(tool_names),
            }
        )
        .execute()
    )
    if not result.data:
        raise AuditLogError("No se pudo registrar la auditoría de la estimación.")
