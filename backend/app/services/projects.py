"""CRUD de proyectos filtrado por el empleado autenticado."""

from uuid import UUID

from supabase import Client

from app.models.project import Project, ProjectCreate, ProjectUpdate


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: UUID) -> None:
        self.project_id = project_id
        super().__init__(f"No existe el proyecto {project_id}.")


class ProjectError(Exception):
    pass


def _row(data: list[dict] | None) -> dict | None:
    if not data:
        return None
    return data[0]


def list_projects(client: Client, created_by: UUID) -> list[Project]:
    result = (
        client.table("projects")
        .select("*")
        .eq("created_by", str(created_by))
        .order("updated_at", desc=True)
        .execute()
    )
    return [Project.model_validate(item) for item in (result.data or [])]


def get_project(client: Client, project_id: UUID, created_by: UUID) -> Project:
    result = (
        client.table("projects")
        .select("*")
        .eq("id", str(project_id))
        .eq("created_by", str(created_by))
        .limit(1)
        .execute()
    )
    row = _row(result.data)
    if row is None:
        raise ProjectNotFoundError(project_id)
    return Project.model_validate(row)


def create_project(
    client: Client, created_by: UUID, payload: ProjectCreate
) -> Project:
    insert: dict[str, object] = {
        "name": payload.name,
        "status": payload.status,
        "created_by": str(created_by),
    }
    if payload.budget is not None:
        insert["budget"] = str(payload.budget)
    result = client.table("projects").insert(insert).execute()
    row = _row(result.data)
    if row is None:
        raise ProjectError("No se pudo crear el proyecto.")
    return Project.model_validate(row)


def update_project(
    client: Client, project_id: UUID, created_by: UUID, payload: ProjectUpdate
) -> Project:
    patch = payload.as_patch()
    if not patch:
        return get_project(client, project_id, created_by)
    result = (
        client.table("projects")
        .update(patch)
        .eq("id", str(project_id))
        .eq("created_by", str(created_by))
        .execute()
    )
    row = _row(result.data)
    if row is None:
        raise ProjectNotFoundError(project_id)
    return Project.model_validate(row)
