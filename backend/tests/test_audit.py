"""Persistencia de `audit_logs` al cerrar una corrida del agente."""

from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.audit import AuditLogError, record_estimation_audit, summarize_tools


def test_summarize_tools_lists_the_trace() -> None:
    summary = summarize_tools(
        ["diagnosticar_sistema", "resolver_por_gauss", "resolver_por_gauss"]
    )
    assert summary.startswith("3 llamada(s):")
    assert "diagnosticar_sistema → resolver_por_gauss → resolver_por_gauss" in summary


def test_summarize_tools_empty() -> None:
    assert "ninguna herramienta" in summarize_tools([])


def test_record_estimation_audit_inserts_expected_columns() -> None:
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": str(uuid4())}]
    )
    employee_id = UUID("3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f")
    project_id = uuid4()
    estimation_id = uuid4()

    record_estimation_audit(
        client,
        employee_id=employee_id,
        project_id=project_id,
        estimation_id=estimation_id,
        tool_names=["diagnosticar_sistema", "buscar_conocimiento"],
    )

    client.table.assert_called_once_with("audit_logs")
    payload = client.table.return_value.insert.call_args.args[0]
    assert payload["employee_id"] == str(employee_id)
    assert payload["project_id"] == str(project_id)
    assert payload["estimation_id"] == str(estimation_id)
    assert payload["tools_used"] == ["diagnosticar_sistema", "buscar_conocimiento"]
    assert "diagnosticar_sistema → buscar_conocimiento" in payload["tools_summary"]


def test_record_estimation_audit_raises_when_insert_returns_nothing() -> None:
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with pytest.raises(AuditLogError):
        record_estimation_audit(
            client,
            employee_id=uuid4(),
            project_id=uuid4(),
            estimation_id=uuid4(),
            tool_names=[],
        )
