"""Integración HTTP: crear estimación, generar informe y buscar en el RAG."""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.supabase import get_supabase_client
from app.main import app
from app.models.agent import AgentRunRequest
from app.services.report_generator import mock_pdf_renderer
from tests.auth_utils import FakeJWKSClient, generate_keypair, sign_token
from tests.fixtures import techchip
from tests.test_agent import fake_supabase as persist_supabase
from tests.test_agent_scenarios import ProtocolLLM
from tests.test_report_generator import _estimation_row

PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

EMPLOYEE_ROW = {
    "id": "3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f",
    "clerk_user_id": "user_123",
    "name": "Ada Lovelace",
    "role": "estimator",
    "created_at": "2026-09-15T00:00:00+00:00",
}

client = TestClient(app)


@pytest.fixture
def supabase() -> MagicMock:
    supabase_client = MagicMock()
    select = (
        supabase_client.table.return_value.select.return_value.eq.return_value.limit.return_value
    )
    select.execute.return_value = MagicMock(data=[EMPLOYEE_ROW])
    app.dependency_overrides[get_supabase_client] = lambda: supabase_client
    yield supabase_client
    app.dependency_overrides.pop(get_supabase_client, None)


@pytest.fixture(autouse=True)
def fake_jwks():
    with patch(
        "app.core.security.get_jwks_client", return_value=FakeJWKSClient(PUBLIC_KEY)
    ):
        yield


def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {sign_token(PRIVATE_KEY)}"}


def _combined_store() -> MagicMock:
    """Auth (employees) + inserts de estimations/audit_logs."""
    store = persist_supabase()
    persist_table = store.table.side_effect

    employees = MagicMock()
    employees.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=[EMPLOYEE_ROW])
    )

    def table(name: str) -> MagicMock:
        if name == "employees":
            return employees
        return persist_table(name)

    store.table.side_effect = table
    return store


@patch("app.services.agent.get_anthropic_client")
def test_crear_estimacion_corre_el_agente_y_audita(mock_anthropic: MagicMock) -> None:
    request = AgentRunRequest(
        problem_text="¿Qué plan de producción cabe en la planta este turno?",
        project_id=uuid4(),
        A=techchip.A,
        B=techchip.DATASET_B,
        variable_names=techchip.VARIABLE_NAMES,
        resource_names=techchip.RESOURCE_NAMES,
    )
    mock_anthropic.return_value = ProtocolLLM(
        {
            "A": techchip.A,
            "B": techchip.DATASET_B,
            "variable_names": techchip.VARIABLE_NAMES,
        },
        request,
    )
    store = _combined_store()
    app.dependency_overrides[get_supabase_client] = lambda: store
    try:
        response = client.post(
            "/api/v1/agent/run",
            json={
                "problem_text": request.problem_text,
                "project_id": str(request.project_id),
                "A": techchip.A,
                "B": techchip.DATASET_B,
                "variable_names": techchip.VARIABLE_NAMES,
                "resource_names": techchip.RESOURCE_NAMES,
            },
            headers=auth_header(),
        )
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["estimation_id"]
    assert "ejecutable" in body["final_response"].lower()
    assert body["result_json"]["tools"][0]["name"] == "diagnosticar_sistema"
    assert "estimations" in store.inserts
    assert "audit_logs" in store.inserts
    assert store.inserts["audit_logs"]["employee_id"] == EMPLOYEE_ROW["id"]


@patch(
    "app.services.report_generator.render_pdf",
    side_effect=lambda html, renderer=None: mock_pdf_renderer(html),
)
def test_generar_informe_sube_docx_y_pdf(mock_pdf: MagicMock) -> None:
    row = _estimation_row(
        A=techchip.A,
        B=techchip.DATASET_B,
        final_response="Plan ejecutable con las seis líneas de producto.",
        variable_names=techchip.VARIABLE_NAMES,
    )
    estimation_id = UUID(row["id"])
    generated_at = "2026-09-19T04:00:00+00:00"
    report_rows = [
        {
            "id": str(uuid4()),
            "file_url": "https://signed.example/informe.docx",
            "file_type": "docx",
            "generated_at": generated_at,
        },
        {
            "id": str(uuid4()),
            "file_url": "https://signed.example/informe.pdf",
            "file_type": "pdf",
            "generated_at": generated_at,
        },
    ]

    employees = MagicMock()
    employees.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=[EMPLOYEE_ROW])
    )
    estimations = MagicMock()
    estimations.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=[row])
    )
    reports = MagicMock()
    reports.insert.return_value.execute.return_value = MagicMock(data=report_rows)

    supabase_client = MagicMock()

    def table(name: str) -> MagicMock:
        return {"employees": employees, "estimations": estimations, "reports": reports}[
            name
        ]

    supabase_client.table.side_effect = table
    bucket = supabase_client.storage.from_.return_value

    def _signed(path: str, _ttl: int, options=None):
        name = str(path).rsplit("/", 1)[-1]
        return {"signedURL": f"https://signed.example/{name}"}

    bucket.create_signed_url.side_effect = _signed

    app.dependency_overrides[get_supabase_client] = lambda: supabase_client
    try:
        response = client.post(
            f"/api/v1/estimations/{estimation_id}/report", headers=auth_header()
        )
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert response.status_code == 200, response.text
    types = {item["file_type"] for item in response.json()["reports"]}
    assert types == {"docx", "pdf"}
    assert bucket.upload.call_count == 2
    mock_pdf.assert_called()


@patch("app.services.rag.embed_texts")
def test_busqueda_rag_por_http(mock_embed: MagicMock, supabase) -> None:
    mock_embed.return_value = [[0.2] * 512]
    supabase.rpc.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb",
                "content": "Litografía EUV: recurso de la fila 1.",
                "metadata": {"obsidian_path": "recursos.md", "title": "Recursos"},
                "similarity": 0.8,
            }
        ]
    )

    response = client.get(
        "/api/v1/knowledge/search",
        params={"q": "litografía EUV"},
        headers=auth_header(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["query"] == "litografía EUV"
    assert body["results"][0]["metadata"]["obsidian_path"] == "recursos.md"
    supabase.rpc.assert_called_once()
