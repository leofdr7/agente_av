"""Orquestación del agente: despacho de tools con el motor real y Anthropic simulado."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.agent import AgentRunRequest
from app.models.linear_system import SolutionMethod, SystemClassification
from app.services.agent import (
    MAX_ROUNDS,
    SYSTEM_PROMPT,
    TOOL_BUSCAR_CONOCIMIENTO,
    TOOL_DIAGNOSTICAR_SISTEMA,
    TOOL_RESOLVER_GAUSS,
    TOOL_RESOLVER_GAUSS_JORDAN,
    TOOL_RESOLVER_MATRIZ_INVERSA,
    TOOL_SCHEMAS,
    AgentError,
    AgentRun,
    run_agent,
)
from app.services.linear_systems_engine import RAW_MATERIAL_CONSTRAINT
from tests.fixtures import techchip

ESTIMATION_ID = "9c5f1b2a-1111-4c3d-9d5a-1c2b3a4d5e6f"
EMPLOYEE_ID = UUID("3f6c1b1e-6c2c-4d8e-9d5a-1c2b3a4d5e6f")
MODEL = "claude-sonnet-5"


def make_request(**overrides) -> AgentRunRequest:
    payload = {
        "problem_text": "¿Cuántas unidades de cada módulo podemos producir este turno?",
        "project_id": uuid4(),
        "A": techchip.A,
        "B": techchip.DATASET_B,
        "variable_names": techchip.VARIABLE_NAMES,
        "resource_names": techchip.RESOURCE_NAMES,
    }
    payload.update(overrides)
    return AgentRunRequest(**payload)


def make_run(**overrides) -> AgentRun:
    return AgentRun(make_request(**overrides), MODEL)


def system_payload(B: list[float] | None = None) -> dict:
    return {
        "A": techchip.A,
        "B": techchip.DATASET_B if B is None else B,
        "variable_names": techchip.VARIABLE_NAMES,
    }


def singular_A() -> list[list[float]]:
    degenerate = [list(row) for row in techchip.A]
    degenerate[5] = [2 * value for value in techchip.A[0]]
    return degenerate


# -- contrato de las tools ---------------------------------------------------------


def test_expone_las_cinco_tools_del_brief() -> None:
    assert [tool["name"] for tool in TOOL_SCHEMAS] == [
        TOOL_BUSCAR_CONOCIMIENTO,
        TOOL_DIAGNOSTICAR_SISTEMA,
        TOOL_RESOLVER_GAUSS,
        TOOL_RESOLVER_GAUSS_JORDAN,
        TOOL_RESOLVER_MATRIZ_INVERSA,
    ]
    for tool in TOOL_SCHEMAS:
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"


def test_system_prompt_prohibe_calcular_y_exige_diagnosticar_primero() -> None:
    assert "NUNCA resuelvas el sistema de ecuaciones AX=B por tu cuenta" in SYSTEM_PROMPT
    assert "SIEMPRE llama primero a `diagnosticar_sistema`" in SYSTEM_PROMPT
    assert "restricción de materias primas" in SYSTEM_PROMPT
    assert "linealmente dependientes" in SYSTEM_PROMPT


# -- despacho sobre el motor real --------------------------------------------------


def test_diagnosticar_sistema_clasifica_el_caso_techchip() -> None:
    output, is_error = make_run().execute(TOOL_DIAGNOSTICAR_SISTEMA, system_payload())

    assert is_error is False
    assert output["classification"] == SystemClassification.COMPATIBLE_DETERMINADO.value
    assert output["is_singular"] is False
    assert output["determinant"] == pytest.approx(techchip.DET_A, abs=1e-6)


def test_resolver_por_gauss_devuelve_el_plan_esperado_con_pasos() -> None:
    output, is_error = make_run().execute(TOOL_RESOLVER_GAUSS, system_payload())

    assert is_error is False
    assert output["metodo"] == SolutionMethod.GAUSS.value
    assert output["solution"] == pytest.approx(techchip.X_ESPERADA, abs=1e-6)
    assert output["steps"], "la traza de operaciones de fila no puede venir vacía"
    assert output["component_steps"]
    # La validación cruzada solo aparece cuando están los tres métodos.
    assert "validacion_cruzada" not in output


def test_los_tres_metodos_disparan_la_validacion_cruzada_en_el_ultimo() -> None:
    run = make_run()

    for tool in (TOOL_RESOLVER_GAUSS, TOOL_RESOLVER_GAUSS_JORDAN):
        output, is_error = run.execute(tool, system_payload())
        assert is_error is False
        assert "validacion_cruzada" not in output

    output, is_error = run.execute(TOOL_RESOLVER_MATRIZ_INVERSA, system_payload())

    assert is_error is False
    assert output["inverse_matrix"]
    report = output["validacion_cruzada"]
    assert report["coincidencia"] is True
    assert report["informe"]["passed"] is True
    assert report["sustitucion"]["within_tolerance"] is True
    assert report["factibilidad"]["infeasible"] is False
    assert run.cross_validation.solution == pytest.approx(techchip.X_ESPERADA, abs=1e-6)


def test_escasez_de_resina_se_marca_infactible_para_que_el_modelo_lo_traduzca() -> None:
    scarce = list(techchip.DATASET_B)
    scarce[techchip.SCARCITY_RESOURCE_INDEX] = techchip.SCARCITY_VALUE
    run = make_run(B=scarce)

    for tool in (TOOL_RESOLVER_GAUSS, TOOL_RESOLVER_GAUSS_JORDAN):
        run.execute(tool, system_payload(scarce))
    output, is_error = run.execute(TOOL_RESOLVER_MATRIZ_INVERSA, system_payload(scarce))

    assert is_error is False
    factibilidad = output["validacion_cruzada"]["factibilidad"]
    assert factibilidad["infeasible"] is True
    assert factibilidad["reason_code"] == RAW_MATERIAL_CONSTRAINT
    # El motor nombra el recurso/línea afectada; el agente lo traduce a negocio.
    assert any(
        component["label"] in techchip.VARIABLE_NAMES
        for component in factibilidad["components"]
    )


@pytest.mark.parametrize(
    "tool",
    [TOOL_RESOLVER_GAUSS, TOOL_RESOLVER_GAUSS_JORDAN, TOOL_RESOLVER_MATRIZ_INVERSA],
)
def test_sistema_singular_no_llega_al_solver_ni_devuelve_x(tool: str) -> None:
    """Guardrail: aunque el modelo se salte el diagnóstico, no obtiene una solución."""
    payload = {"A": singular_A(), "B": techchip.DATASET_B}
    solver = MagicMock()

    with patch.dict("app.services.agent._SOLVERS", {tool: solver}):
        output, is_error = make_run(A=payload["A"], B=payload["B"]).execute(tool, payload)

    solver.assert_not_called()
    assert is_error is True
    assert "solution" not in output
    assert output["diagnostico"]["is_singular"] is True
    assert output["diagnostico"]["classification"] == (
        SystemClassification.INCOMPATIBLE.value
    )


def test_diagnostico_singular_instruye_a_no_resolver() -> None:
    payload = {"A": singular_A(), "B": techchip.DATASET_B}

    output, is_error = make_run(**payload).execute(TOOL_DIAGNOSTICAR_SISTEMA, payload)

    assert is_error is False
    assert output["is_singular"] is True
    assert "no llames a las herramientas de resolución" in output["instruccion"]


def test_argumentos_invalidos_se_devuelven_como_error_de_tool() -> None:
    output, is_error = make_run().execute(
        TOOL_DIAGNOSTICAR_SISTEMA, {"A": [[1, 2], [3, 4]], "B": [1, 2, 3]}
    )

    assert is_error is True
    assert "no forman un sistema válido" in output["error"]


def test_herramienta_desconocida_no_rompe_el_loop() -> None:
    output, is_error = make_run().execute("resolver_por_intuicion", {})

    assert is_error is True
    assert "Herramienta desconocida" in output["error"]


@patch("app.services.agent.search_knowledge")
def test_buscar_conocimiento_consulta_el_rag(mock_search: MagicMock) -> None:
    mock_search.return_value = [
        SimpleNamespace(
            content="La resina de encapsulado es el recurso más restrictivo.",
            metadata={"obsidian_path": "recursos.md", "title": "Recursos"},
            similarity=0.91,
        )
    ]

    output, is_error = make_run().execute(
        TOOL_BUSCAR_CONOCIMIENTO, {"query": "resina de encapsulado", "top_k": 3}
    )

    assert is_error is False
    mock_search.assert_called_once_with("resina de encapsulado", top_k=3)
    assert output["resultados"][0]["fuente"] == "recursos.md"
    assert output["resultados"][0]["similitud"] == 0.91


def test_buscar_conocimiento_exige_query() -> None:
    output, is_error = make_run().execute(TOOL_BUSCAR_CONOCIMIENTO, {"query": "  "})

    assert is_error is True
    assert "`query` es obligatoria" in output["error"]


# -- loop de conversación ----------------------------------------------------------


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def tool_block(name: str, payload: dict, block_id: str = "toolu_1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=payload)


def turn(*blocks: SimpleNamespace, stop_reason: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def fake_llm(*turns: SimpleNamespace) -> MagicMock:
    llm = MagicMock()
    llm.messages.create.side_effect = list(turns)
    return llm


def fake_supabase() -> MagicMock:
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": ESTIMATION_ID}]
    )
    return client


ANALISIS = "Plan ejecutable: 15 mil AI-Edge 1, 20 mil AI-Server Pro, ..."


def test_loop_ejecuta_las_tools_y_persiste_la_corrida() -> None:
    llm = fake_llm(
        turn(tool_block(TOOL_DIAGNOSTICAR_SISTEMA, system_payload(), "toolu_1")),
        turn(
            tool_block(TOOL_RESOLVER_GAUSS, system_payload(), "toolu_2"),
            tool_block(TOOL_RESOLVER_GAUSS_JORDAN, system_payload(), "toolu_3"),
            tool_block(TOOL_RESOLVER_MATRIZ_INVERSA, system_payload(), "toolu_4"),
        ),
        turn(text_block(ANALISIS), stop_reason="end_turn"),
    )
    supabase = fake_supabase()
    request = make_request()

    response = run_agent(
        request, EMPLOYEE_ID, anthropic_client=llm, supabase=supabase
    )

    assert response.estimation_id == UUID(ESTIMATION_ID)
    assert response.final_response == ANALISIS

    trace = response.result_json
    assert [call.name for call in trace.tools] == [
        TOOL_DIAGNOSTICAR_SISTEMA,
        TOOL_RESOLVER_GAUSS,
        TOOL_RESOLVER_GAUSS_JORDAN,
        TOOL_RESOLVER_MATRIZ_INVERSA,
    ]
    assert all(call.is_error is False for call in trace.tools)
    assert trace.A == techchip.A
    assert trace.B == techchip.DATASET_B
    assert trace.cross_validation.passed is True
    assert trace.substitution.within_tolerance is True
    assert trace.feasibility.infeasible is False
    assert trace.model == MODEL

    # El system prompt y las tools viajan en cada llamada al modelo.
    first_call = llm.messages.create.call_args_list[0].kwargs
    assert first_call["system"] == SYSTEM_PROMPT
    assert first_call["tools"] == TOOL_SCHEMAS
    assert "Sistema entregado ya estructurado" in first_call["messages"][0]["content"]

    inserted = supabase.table.return_value.insert.call_args.args[0]
    assert inserted["problem_text"] == request.problem_text
    assert inserted["project_id"] == str(request.project_id)
    assert inserted["requested_by"] == str(EMPLOYEE_ID)
    assert inserted["result_json"]["final_response"] == ANALISIS
    assert inserted["result_json"]["A"] == techchip.A
    assert len(inserted["result_json"]["tools"]) == 4


def test_loop_devuelve_los_resultados_de_las_tools_al_modelo() -> None:
    llm = fake_llm(
        turn(tool_block(TOOL_DIAGNOSTICAR_SISTEMA, system_payload())),
        turn(text_block(ANALISIS), stop_reason="end_turn"),
    )

    run_agent(make_request(), EMPLOYEE_ID, anthropic_client=llm, supabase=fake_supabase())

    second_call = llm.messages.create.call_args_list[1].kwargs
    messages = second_call["messages"]
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"][0]["type"] == "tool_use"
    result = messages[2]["content"][0]
    assert messages[2]["role"] == "user"
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_1"
    assert result["is_error"] is False
    assert "compatible_determinado" in result["content"]


def test_sin_matriz_el_mensaje_pide_extraer_los_coeficientes() -> None:
    llm = fake_llm(turn(text_block(ANALISIS), stop_reason="end_turn"))

    run_agent(
        make_request(A=None, B=None),
        EMPLOYEE_ID,
        anthropic_client=llm,
        supabase=fake_supabase(),
    )

    prompt = llm.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "extrae los coeficientes" in prompt
    assert "No resuelvas nada por tu cuenta" in prompt


def test_loop_se_detiene_tras_el_tope_de_rondas() -> None:
    llm = MagicMock()
    llm.messages.create.return_value = turn(
        tool_block(TOOL_DIAGNOSTICAR_SISTEMA, system_payload())
    )
    supabase = fake_supabase()

    with pytest.raises(AgentError, match=f"{MAX_ROUNDS} rondas"):
        run_agent(
            make_request(), EMPLOYEE_ID, anthropic_client=llm, supabase=supabase
        )

    assert llm.messages.create.call_count == MAX_ROUNDS
    supabase.table.return_value.insert.assert_not_called()


def test_a_y_b_deben_venir_juntos() -> None:
    with pytest.raises(ValueError, match="A y B deben entregarse juntos"):
        make_request(B=None)
