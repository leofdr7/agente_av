"""Orquestación del agente: despacho de tools con el motor real y Anthropic simulado."""

import json
import os
import unicodedata
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import numpy as np
import pytest

from app.core.config import settings
from app.models.agent import AgentRunRequest
from app.models.linear_system import SolutionMethod, SystemClassification
from app.services.agent import (
    MAX_ROUNDS,
    PROTOCOL_DIAGNOSE_FIRST,
    PROTOCOL_SOLVE_BEFORE_NUMBERS,
    SYSTEM_PROMPT,
    TOOL_BUSCAR_CONOCIMIENTO,
    TOOL_DIAGNOSTICAR_SISTEMA,
    TOOL_RESOLVER_GAUSS,
    TOOL_RESOLVER_GAUSS_JORDAN,
    TOOL_RESOLVER_MATRIZ_INVERSA,
    TOOL_SCHEMAS,
    AgentError,
    AgentRun,
    _initial_message,
    get_anthropic_client,
    looks_like_numeric_solution,
    run_agent,
)
from app.services.linear_systems_engine import NEGATIVE_SOLUTION_COMPONENT
from tests.fixtures import panaderia, techchip

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


# Vocabulario que asume manufactura: el modelo lee las tools antes de resolver, así que
# aquí sesgaría su interpretación igual que lo haría el system prompt.
DOMINIO_FIJO = [
    "planta",
    "línea de producto",
    "línea de producción",
    "disponibilidades",
    "materia",
    "recurso de la",
]


def test_las_descripciones_de_las_tools_hablan_en_terminos_matematicos() -> None:
    schemas = json.dumps(TOOL_SCHEMAS, ensure_ascii=False).lower()
    for termino in DOMINIO_FIJO:
        assert termino not in schemas

    sistema = TOOL_SCHEMAS[1]["input_schema"]["properties"]
    assert "matriz de coeficientes cuadrada nxn del sistema ax=b" in sistema["A"]["description"].lower()
    assert "cada fila es una ecuación" in sistema["A"]["description"].lower()
    assert "términos independientes" in sistema["B"]["description"].lower()
    assert "variables x1..xn" in sistema["variable_names"]["description"].lower()
    assert "si el usuario los proporcionó" in sistema["variable_names"]["description"].lower()


def test_el_mensaje_inicial_presenta_las_etiquetas_como_filas_y_columnas() -> None:
    prompt = _initial_message(make_request(problem_text="Resuelve el sistema adjunto."))

    assert "Nombres de las columnas de A (variables x1..xn)" in prompt
    assert "Nombres de las filas de A (ecuaciones del sistema)" in prompt
    # Los nombres del caso llegan como datos del usuario, no como vocabulario impuesto.
    assert techchip.RESOURCE_NAMES[0] in prompt
    for termino in DOMINIO_FIJO:
        assert termino not in prompt.lower()


def test_system_prompt_prohibe_calcular_y_exige_diagnosticar_primero() -> None:
    assert "NUNCA resuelvas el sistema de ecuaciones AX=B por tu cuenta" in SYSTEM_PROMPT
    assert "SIEMPRE llama primero a `diagnosticar_sistema`" in SYSTEM_PROMPT
    assert "linealmente dependientes" in SYSTEM_PROMPT


def test_system_prompt_ordena_las_fuentes_de_terminologia_sin_fijar_un_dominio() -> None:
    prioridades = [
        SYSTEM_PROMPT.index("`resource_names`"),
        SYSTEM_PROMPT.index("`buscar_conocimiento`", SYSTEM_PROMPT.index("`resource_names`")),
        SYSTEM_PROMPT.index("los términos que el propio usuario usó"),
    ]
    assert prioridades == sorted(prioridades)
    assert "`variable_names`" in SYSTEM_PROMPT
    assert "solo si esos resultados son" in SYSTEM_PROMPT
    assert (
        "NUNCA asumas ni fuerces la terminología de un negocio, empresa o industria que el"
        in SYSTEM_PROMPT
    )


def test_system_prompt_traduce_el_reason_code_neutro_con_la_cadena_de_prioridad() -> None:
    assert NEGATIVE_SOLUTION_COMPONENT in SYSTEM_PROMPT
    assert "NO lo leas como una restricción de materia prima" in SYSTEM_PROMPT
    # La traducción del código apela a la misma cadena que el resto del prompt.
    cadena = SYSTEM_PROMPT.index("`resource_names`")
    assert SYSTEM_PROMPT.index("aplicando la cadena de prioridad de arriba") > cadena


def test_system_prompt_no_impone_la_terminologia_de_un_caso_concreto() -> None:
    for termino in techchip.RESOURCE_NAMES + techchip.VARIABLE_NAMES:
        assert termino.lower() not in SYSTEM_PROMPT.lower()
    assert "TechChip" not in SYSTEM_PROMPT


def test_system_prompt_pide_el_markdown_que_el_frontend_y_los_informes_renderizan() -> None:
    formato = SYSTEM_PROMPT[SYSTEM_PROMPT.index("FORMATO DE LA RESPUESTA FINAL") :]

    assert "Markdown" in formato
    assert "`##`" in formato
    assert "`**texto**`" in formato
    assert "|---|" in formato


def test_system_prompt_prohibe_el_latex_que_el_frontend_no_puede_renderizar() -> None:
    formato = SYSTEM_PROMPT[SYSTEM_PROMPT.index("FORMATO DE LA RESPUESTA FINAL") :]

    assert "No uses notación LaTeX" in formato
    assert "$$...$$" in formato
    assert r"\begin{pmatrix}" in formato
    # La alternativa para matrices tiene que quedar dicha, no solo la prohibición.
    assert "tabla Markdown o un bloque de código" in formato


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
    assert factibilidad["reason_code"] == NEGATIVE_SOLUTION_COMPONENT
    # El motor solo reporta el hecho matemático y la etiqueta que le pasaron; la
    # interpretación de qué recurso lo provoca queda en manos del agente.
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
    inserts: dict[str, dict] = {}

    def table(name: str) -> MagicMock:
        handle = MagicMock()

        def insert(payload: dict) -> MagicMock:
            inserts[name] = payload
            result = MagicMock()
            result.execute.return_value = MagicMock(data=[{"id": ESTIMATION_ID}])
            return result

        handle.insert.side_effect = insert
        return handle

    client.table.side_effect = table
    client.inserts = inserts
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

    inserted = supabase.inserts["estimations"]
    assert inserted["problem_text"] == request.problem_text
    assert inserted["project_id"] == str(request.project_id)
    assert inserted["requested_by"] == str(EMPLOYEE_ID)
    assert inserted["result_json"]["final_response"] == ANALISIS
    assert inserted["result_json"]["A"] == techchip.A
    assert len(inserted["result_json"]["tools"]) == 4

    audit = supabase.inserts["audit_logs"]
    assert audit["employee_id"] == str(EMPLOYEE_ID)
    assert audit["project_id"] == str(request.project_id)
    assert audit["estimation_id"] == ESTIMATION_ID
    assert audit["tools_used"] == [
        TOOL_DIAGNOSTICAR_SISTEMA,
        TOOL_RESOLVER_GAUSS,
        TOOL_RESOLVER_GAUSS_JORDAN,
        TOOL_RESOLVER_MATRIZ_INVERSA,
    ]
    assert "diagnosticar_sistema" in audit["tools_summary"]


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
    prompt = _initial_message(make_request(A=None, B=None))
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
    assert "estimations" not in supabase.inserts


def test_a_y_b_deben_venir_juntos() -> None:
    with pytest.raises(ValueError, match="A y B deben entregarse juntos"):
        make_request(B=None)


def test_looks_like_numeric_solution_detecta_un_vector_x() -> None:
    assert looks_like_numeric_solution("La solución es X = (15, 20, 25, 10, 15, 20)")
    assert looks_like_numeric_solution("x1=15, x2=20")
    assert not looks_like_numeric_solution(ANALISIS)


def test_loop_rechaza_resolver_antes_de_diagnosticar() -> None:
    llm = fake_llm(
        turn(tool_block(TOOL_RESOLVER_GAUSS, system_payload(), "toolu_skip")),
        turn(tool_block(TOOL_DIAGNOSTICAR_SISTEMA, system_payload(), "toolu_diag")),
        turn(text_block("Diagnóstico recibido; el sistema es compatible determinado."), stop_reason="end_turn"),
    )

    response = run_agent(
        make_request(), EMPLOYEE_ID, anthropic_client=llm, supabase=fake_supabase()
    )

    assert response.result_json.tools[0].name == TOOL_RESOLVER_GAUSS
    assert response.result_json.tools[0].is_error is True
    assert PROTOCOL_DIAGNOSE_FIRST in response.result_json.tools[0].output["error"]
    assert "solution" not in (response.result_json.tools[0].output or {})
    assert response.result_json.tools[1].name == TOOL_DIAGNOSTICAR_SISTEMA
    assert response.result_json.tools[1].is_error is False


def test_loop_rechaza_un_vector_x_sin_haber_resuelto() -> None:
    llm = fake_llm(
        turn(tool_block(TOOL_DIAGNOSTICAR_SISTEMA, system_payload())),
        turn(
            text_block("X = (15, 20, 25, 10, 15, 20)"),
            stop_reason="end_turn",
        ),
        turn(
            tool_block(TOOL_RESOLVER_GAUSS, system_payload(), "toolu_g"),
            tool_block(TOOL_RESOLVER_GAUSS_JORDAN, system_payload(), "toolu_gj"),
            tool_block(TOOL_RESOLVER_MATRIZ_INVERSA, system_payload(), "toolu_inv"),
        ),
        turn(text_block(ANALISIS), stop_reason="end_turn"),
    )

    response = run_agent(
        make_request(), EMPLOYEE_ID, anthropic_client=llm, supabase=fake_supabase()
    )

    reminders = [
        message["content"]
        for call in llm.messages.create.call_args_list
        for message in call.kwargs["messages"]
        if message.get("role") == "user" and isinstance(message.get("content"), str)
    ]
    assert any(PROTOCOL_SOLVE_BEFORE_NUMBERS in text for text in reminders)
    names = [call.name for call in response.result_json.tools]
    assert names[0] == TOOL_DIAGNOSTICAR_SISTEMA
    assert TOOL_RESOLVER_GAUSS in names
    assert response.final_response == ANALISIS
    assert response.result_json.cross_validation is not None


# -- generalización: panadería, independiente de TechChip -------------------------

TERMINOS_DEL_ENUNCIADO = ("harina", "horno", "pan de caja", "baguette", "bolillo")


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto.lower())
    return "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")


def _contiene(texto: str, termino: str) -> bool:
    return _sin_acentos(termino) in _sin_acentos(texto)


def test_panaderia_numpy_coincide_con_la_solucion_de_referencia() -> None:
    """Resolución independiente del fixture, sin pasar por el modelo."""
    solucion = np.linalg.solve(
        np.array(panaderia.A, dtype=float),
        np.array(panaderia.B, dtype=float),
    )

    assert solucion == pytest.approx(panaderia.X_ESPERADA, abs=1e-6)
    assert len(techchip.A) != len(panaderia.A)
    assert "[[" not in panaderia.PROBLEM_TEXT


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AGENT") != "1",
    reason="Corrida real contra Anthropic; ejecutar con RUN_LIVE_AGENT=1",
)
def test_panaderia_corrida_real_extrae_el_sistema_sin_vocabulario_techchip() -> None:
    """Extrae el 3x3 del enunciado, lo resuelve y no arrastra TechChip ni el RAG vacío."""
    if "example.supabase.co" in settings.supabase_url:
        pytest.fail(
            "SUPABASE_URL apunta al host de tests. Carga backend/.env en el "
            "entorno antes de pytest para que buscar_conocimiento use el vault real."
        )
    if not settings.anthropic_api_key:
        pytest.fail("Falta ANTHROPIC_API_KEY en el entorno.")
    if settings.embedding_provider == "voyage" and not settings.voyage_api_key:
        pytest.fail("Falta VOYAGE_API_KEY; buscar_conocimiento no puede embeber la consulta.")
    if settings.embedding_provider == "openai" and not settings.openai_api_key:
        pytest.fail("Falta OPENAI_API_KEY; buscar_conocimiento no puede embeber la consulta.")

    response = run_agent(
        AgentRunRequest(problem_text=panaderia.PROBLEM_TEXT, project_id=uuid4()),
        EMPLOYEE_ID,
        anthropic_client=get_anthropic_client(),
        supabase=fake_supabase(),
    )
    trace = response.result_json

    assert trace.A == panaderia.A, trace.A
    assert trace.B == panaderia.B, trace.B
    independiente = np.linalg.solve(
        np.array(trace.A, dtype=float),
        np.array(trace.B, dtype=float),
    )
    assert independiente == pytest.approx(panaderia.X_ESPERADA, abs=1e-6)
    assert trace.cross_validation is not None
    assert trace.cross_validation.solution == pytest.approx(panaderia.X_ESPERADA, abs=1e-6)

    for termino in TERMINOS_DEL_ENUNCIADO:
        assert _contiene(response.final_response, termino), response.final_response
    for termino in panaderia.TERMINOS_PROHIBIDOS:
        assert not _contiene(response.final_response, termino), response.final_response

    consultas = [
        record
        for record in trace.tools
        if record.name == TOOL_BUSCAR_CONOCIMIENTO
    ]
    assert consultas, "el agente no consultó la base de conocimiento"
    # La consulta busca notas del proceso; no tiene que repetir cada pan.
    # El enunciado ya pide eso, y los tres panes se exigen en la interpretación.
    texto_consultas = "\n".join(str(record.input.get("query", "")) for record in consultas)
    for termino in ("harina", "horno"):
        assert _contiene(texto_consultas, termino), texto_consultas
    for record in consultas:
        assert record.is_error is False, record.output
        assert record.output["resultados"] == [], record.output
        consulta = str(record.input.get("query", ""))
        for termino in panaderia.TERMINOS_PROHIBIDOS:
            assert not _contiene(consulta, termino), consulta

