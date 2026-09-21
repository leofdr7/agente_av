"""Los 4 escenarios TechChip reproducidos a nivel de agente (LLM simulado + motor real)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.models.agent import AgentRunRequest
from app.models.linear_system import SystemClassification
from app.services.agent import (
    TOOL_DIAGNOSTICAR_SISTEMA,
    TOOL_RESOLVER_GAUSS,
    TOOL_RESOLVER_GAUSS_JORDAN,
    TOOL_RESOLVER_MATRIZ_INVERSA,
    run_agent,
)
from app.services.linear_systems_engine import NEGATIVE_SOLUTION_COMPONENT, SOLUTION_TOL
from tests.fixtures import techchip
from tests.test_agent import fake_supabase

EMPLOYEE_ID = UUID("3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f")
RESOLUTION_ORDER = (
    TOOL_RESOLVER_GAUSS,
    TOOL_RESOLVER_GAUSS_JORDAN,
    TOOL_RESOLVER_MATRIZ_INVERSA,
)


def _payload(B: list[float] | None = None) -> dict[str, Any]:
    return {
        "A": techchip.A,
        "B": techchip.DATASET_B if B is None else B,
        "variable_names": techchip.VARIABLE_NAMES,
    }


def _degenerate_A() -> list[list[float]]:
    rows = [list(row) for row in techchip.A]
    rows[5] = [2 * value for value in techchip.A[0]]
    return rows


def make_request(**overrides) -> AgentRunRequest:
    payload = {
        "problem_text": "¿Qué plan de producción cabe en la planta este turno?",
        "project_id": uuid4(),
        "A": techchip.A,
        "B": techchip.DATASET_B,
        "variable_names": techchip.VARIABLE_NAMES,
        "resource_names": techchip.RESOURCE_NAMES,
    }
    payload.update(overrides)
    return AgentRunRequest(**payload)


def _block(name: str, payload: dict[str, Any], block_id: str) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=payload)


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _turn(*blocks: SimpleNamespace, stop_reason: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def _parse_pairs(messages: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    pairs: list[tuple[str, dict[str, Any]]] = []
    pending: list[str] = []
    for message in messages:
        content = message.get("content")
        if message.get("role") == "assistant" and isinstance(content, list):
            pending = [
                block["name"]
                for block in content
                if isinstance(block, dict) and block.get("type") == "tool_use"
            ]
        elif message.get("role") == "user" and isinstance(content, list) and pending:
            results = [
                block
                for block in content
                if isinstance(block, dict) and block.get("type") == "tool_result"
            ]
            for name, result in zip(pending, results, strict=False):
                raw = result.get("content")
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                pairs.append((name, parsed if isinstance(parsed, dict) else {}))
            pending = []
    return pairs


def interpret_from_messages(
    messages: list[dict[str, Any]], request: AgentRunRequest
) -> str:
    """Traduce a lenguaje de negocio solo con lo que devolvieron las tools (como Claude)."""
    pairs = _parse_pairs(messages)
    diagnosis: dict[str, Any] = {}
    cross: dict[str, Any] = {}
    for name, output in pairs:
        if name == TOOL_DIAGNOSTICAR_SISTEMA:
            diagnosis = output
        if "validacion_cruzada" in output:
            cross = output["validacion_cruzada"]

    resources = request.resource_names or techchip.RESOURCE_NAMES
    variables = request.variable_names or techchip.VARIABLE_NAMES

    if diagnosis.get("is_singular"):
        litografia = resources[0]
        inspeccion = resources[5]
        return (
            f"El sistema es {diagnosis.get('classification')} "
            f"(det(A)={diagnosis.get('determinant')}) y no tiene solución. "
            f"La {inspeccion} quedó expresada como múltiplo de la {litografia} "
            f"(F6 = 2·F1) y por eso el modelo no tiene solución. "
            "No hay un plan de producción que encaje con estas restricciones."
        )

    factibilidad = cross.get("factibilidad") or {}
    sustitucion = cross.get("sustitucion") or {}
    informe = cross.get("informe") or {}
    solution = informe.get("solution") or []

    if factibilidad.get("infeasible"):
        resin = next(
            (name for name in resources if "resina" in name.lower()),
            "resina de encapsulado",
        )
        negatives = [
            item.get("label") or item.get("variable")
            for item in factibilidad.get("components") or []
        ]
        return (
            "El plan de producción es inalcanzable: el motor marcó "
            f"{factibilidad.get('reason_code')}. "
            f"El recurso restrictivo es la {resin}, según los resource_names "
            "que entregó la solicitud. "
            f"Quedan en negativo: {', '.join(str(item) for item in negatives if item) or variables[0]}. "
            "No presentes esas cantidades como un plan ejecutable."
        )

    labeled = ", ".join(
        f"{name}={value}" for name, value in zip(variables, solution, strict=False)
    )
    error_norm = sustitucion.get("error_norm")
    return (
        "El sistema es compatible determinado y el plan es ejecutable. "
        f"Vector X: {labeled}. "
        f"Error de sustitución ‖AX−B‖={error_norm}, dentro de tolerancia. "
        "Gauss, Gauss-Jordan y la matriz inversa coinciden."
    )


class ProtocolLLM:
    """Claude disciplinado: diagnostica, resuelve si aplica, e interpreta el motor."""

    def __init__(self, payload: dict[str, Any], request: AgentRunRequest) -> None:
        self.payload = payload
        self.request = request
        self.messages = MagicMock()
        self.messages.create.side_effect = self._next

    def _next(self, **kwargs: Any) -> SimpleNamespace:
        messages = kwargs["messages"]
        called = [name for name, _ in _parse_pairs(messages)]

        if TOOL_DIAGNOSTICAR_SISTEMA not in called:
            return _turn(
                _block(TOOL_DIAGNOSTICAR_SISTEMA, self.payload, "toolu_diag")
            )

        diagnosis = next(
            output
            for name, output in _parse_pairs(messages)
            if name == TOOL_DIAGNOSTICAR_SISTEMA
        )
        if diagnosis.get("is_singular"):
            return _turn(
                _text(interpret_from_messages(messages, self.request)),
                stop_reason="end_turn",
            )

        if not all(tool in called for tool in RESOLUTION_ORDER):
            return _turn(
                _block(TOOL_RESOLVER_GAUSS, self.payload, "toolu_g"),
                _block(TOOL_RESOLVER_GAUSS_JORDAN, self.payload, "toolu_gj"),
                _block(TOOL_RESOLVER_MATRIZ_INVERSA, self.payload, "toolu_inv"),
            )

        return _turn(
            _text(interpret_from_messages(messages, self.request)),
            stop_reason="end_turn",
        )


def _run(request: AgentRunRequest, payload: dict[str, Any]):
    llm = ProtocolLLM(payload, request)
    return run_agent(
        request, EMPLOYEE_ID, anthropic_client=llm, supabase=fake_supabase()
    )


def test_agente_siempre_llama_primero_a_diagnosticar_sistema() -> None:
    response = _run(make_request(), _payload())
    names = [call.name for call in response.result_json.tools]
    assert names[0] == TOOL_DIAGNOSTICAR_SISTEMA
    assert all(not call.is_error for call in response.result_json.tools)


def test_agente_prueba_base_x_esperada_y_plan_ejecutable() -> None:
    """Escenario 1: X=(15,20,25,10,15,20) y el agente lo presenta como plan viable."""
    response = _run(make_request(), _payload())
    trace = response.result_json

    assert [call.name for call in trace.tools] == [
        TOOL_DIAGNOSTICAR_SISTEMA,
        *RESOLUTION_ORDER,
    ]
    assert trace.cross_validation is not None
    assert trace.cross_validation.solution == pytest.approx(
        techchip.X_ESPERADA, abs=SOLUTION_TOL
    )
    assert trace.feasibility is not None
    assert trace.feasibility.infeasible is False

    text = response.final_response.lower()
    assert "ejecutable" in text or "compatible determinado" in text
    for value in techchip.X_ESPERADA:
        assert str(int(value)) in response.final_response
    for line in ("AI-Edge 1", "AI-Server Pro"):
        assert line in response.final_response


def test_agente_verifica_error_de_sustitucion() -> None:
    """Escenario 2: ‖AX−B‖ < 1e-6 y el agente lo cita en la interpretación."""
    response = _run(make_request(), _payload())
    trace = response.result_json

    assert trace.substitution is not None
    assert trace.substitution.error_norm < SOLUTION_TOL
    assert trace.substitution.within_tolerance is True
    assert trace.cross_validation is not None
    assert trace.cross_validation.passed is True

    text = response.final_response.lower()
    assert "sustitución" in text or "sustitucion" in text
    assert "tolerancia" in text
    assert "coinciden" in text


def test_agente_escasez_nombra_la_resina_de_encapsulado() -> None:
    """Escenario 3: B3=100; el agente nombra la resina como recurso restrictivo."""
    scarce = list(techchip.DATASET_B)
    scarce[techchip.SCARCITY_RESOURCE_INDEX] = techchip.SCARCITY_VALUE
    request = make_request(
        B=scarce,
        problem_text=(
            "Nos quedamos cortos de resina de encapsulado (B3=100). "
            "¿Qué plan de producción es viable?"
        ),
    )

    response = _run(request, _payload(scarce))
    trace = response.result_json

    assert trace.feasibility is not None
    assert trace.feasibility.infeasible is True
    assert trace.feasibility.reason_code == NEGATIVE_SOLUTION_COMPONENT
    assert any(value < 0 for value in (trace.cross_validation.solution if trace.cross_validation else []))

    text = response.final_response.lower()
    # El nombre del recurso sale de los resource_names de la solicitud, no del
    # reason_code: el motor solo reporta el hecho matemático.
    assert "resina de encapsulado" in text
    assert "restrictiv" in text
    assert "inalcanzable" in text
    assert NEGATIVE_SOLUTION_COMPONENT in text
    assert "no presentes" in text or "no presente" in text


def test_agente_degenerado_explica_f6_como_multiplo_de_f1() -> None:
    """Escenario 4: F6=2*F1; el agente explica la dependencia y no inventa un X."""
    degenerate = _degenerate_A()
    request = make_request(
        A=degenerate,
        problem_text=(
            "La inspección óptica (F6) quedó escrita como el doble de la "
            "litografía EUV (F1). Diagnostica el modelo."
        ),
    )
    payload = {
        "A": degenerate,
        "B": techchip.DATASET_B,
        "variable_names": techchip.VARIABLE_NAMES,
    }

    response = _run(request, payload)
    trace = response.result_json

    assert [call.name for call in trace.tools] == [TOOL_DIAGNOSTICAR_SISTEMA]
    diagnosis = trace.tools[0].output
    assert diagnosis["is_singular"] is True
    assert diagnosis["classification"] == SystemClassification.INCOMPATIBLE.value
    assert trace.cross_validation is None
    assert trace.feasibility is None

    text = response.final_response.lower()
    assert "inspección óptica" in text or "inspeccion optica" in text
    assert "litografía euv" in text or "litografia euv" in text
    assert "múltiplo" in text or "multiplo" in text
    assert "f6" in text and "f1" in text
    assert "no tiene solución" in text or "no tiene solucion" in text
    from app.services.agent import looks_like_numeric_solution

    assert looks_like_numeric_solution(response.final_response) is False
    assert "15, 20, 25" not in response.final_response
