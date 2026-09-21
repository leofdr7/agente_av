"""Orquestador del agente: Claude con tool use sobre el motor determinista y el RAG.

El modelo no calcula. Decide qué herramienta llamar, lee los resultados que devuelve
`linear_systems_engine` y los traduce a lenguaje de negocio (interpretación
semántica). Todo el cálculo vive en el motor; aquí solo se despachan tools, se
compara lo que devuelven y se registra la corrida en `estimations`.

Las herramientas de resolución diagnostican el sistema antes de resolverlo aunque el
modelo no llame a `diagnosticar_sistema`: un sistema singular nunca llega al solver.
"""

import json
import re
from collections.abc import Callable, Sequence
from typing import Any
from uuid import UUID

from anthropic import Anthropic
from pydantic import ValidationError
from supabase import Client

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.models.agent import (
    AgentRunRequest,
    AgentRunResponse,
    AgentRunTrace,
    ToolCallRecord,
)
from app.services.audit import AuditLogError, record_estimation_audit
from app.models.linear_system import LinearSystemInput, MethodSolution, SolutionMethod
from app.services.linear_systems_engine import (
    MethodInconsistencyError,
    SingularSystemError,
    check_feasibility,
    cross_validate_methods,
    solve_gauss,
    solve_gauss_jordan,
    solve_matrix_inverse,
    validate_system,
    verify_solution,
)
from app.services.rag import search_knowledge

# Tope de rondas de tool use: evita que un modelo indeciso cicle indefinidamente.
MAX_ROUNDS = 12
MAX_TOKENS = 8000
DEFAULT_TOP_K = 5

TOOL_BUSCAR_CONOCIMIENTO = "buscar_conocimiento"
TOOL_DIAGNOSTICAR_SISTEMA = "diagnosticar_sistema"
TOOL_RESOLVER_GAUSS = "resolver_por_gauss"
TOOL_RESOLVER_GAUSS_JORDAN = "resolver_por_gauss_jordan"
TOOL_RESOLVER_MATRIZ_INVERSA = "resolver_por_matriz_inversa"

SYSTEM_PROMPT = """\
Eres el agente de estimaciones de AgentA. Interpretas sistemas de ecuaciones lineales
AX=B de cualquier tamaño nxn admitido por el motor, sobre cualquier dominio que el
usuario plantee. Tu trabajo es interpretar, no calcular.

REGLAS ABSOLUTAS
1. NUNCA resuelvas el sistema de ecuaciones AX=B por tu cuenta. Nunca inventes,
   estimes ni "redondees" valores de X. Todo número que presentes debe venir de una
   herramienta.
2. SIEMPRE llama primero a `diagnosticar_sistema`. Es obligatorio antes de cualquier
   intento de resolución.
3. Si el diagnóstico dice `is_singular: true`, DETENTE: no llames a los métodos de
   resolución y no ofrezcas ningún vector solución.
4. Solo si el sistema NO es singular, llama a los tres métodos
   (`resolver_por_gauss`, `resolver_por_gauss_jordan`, `resolver_por_matriz_inversa`)
   y compara sus resultados con el informe de validación cruzada que acompaña al
   tercero (`validacion_cruzada`) antes de redactar tu respuesta.
5. Usa `buscar_conocimiento` cuando necesites terminología o contexto que el enunciado
   no te dé. Trata sus resultados como material de apoyo: úsalos solo si hablan del
   problema que tienes delante y descártalos si no.

INTERPRETACIÓN SEMÁNTICA (tu rol central)
Traduce cada resultado numérico al lenguaje del problema que te plantearon, sin
importar de qué dominio sea.

NUNCA asumas ni fuerces la terminología de un negocio, empresa o industria que el
usuario no haya mencionado. Si no sabes cómo se llama algo, di "la variable x3" o "la
ecuación 4" en lugar de inventarle un nombre.

Para nombrar el recurso o la variable responsable de un resultado, usa la primera de
estas fuentes que aplique, en este orden:
1. Los `resource_names` (filas de A) y `variable_names` (columnas de A) si el usuario
   los entregó en la solicitud. Tienen prioridad sobre cualquier otra fuente.
2. El contexto que devolvió `buscar_conocimiento`, y solo si esos resultados son
   relevantes al problema planteado.
3. Si ninguna de las dos aplica, los términos que el propio usuario usó al describir
   el problema.

Lecturas obligadas de cada resultado del motor:
- `feasibility.infeasible: true` con `reason_code: componente de solucion negativo`:
  ese código es solo el hecho matemático (alguna componente de X salió negativa), no
  una interpretación. NO lo leas como una restricción de materia prima ni como ningún
  otro motivo de negocio por defecto. Nombra la variable en negativo y el recurso o la
  ecuación que la bloquea aplicando la cadena de prioridad de arriba, igual que haces
  con el diagnóstico de singularidad. No presentes la cantidad negativa como un
  resultado válido: explícala como evidencia de que los valores declarados en B no
  admiten una solución realizable.
- `classification: incompatible`: el sistema no tiene solución. Las condiciones
  declaradas en B se contradicen entre sí; no existe ninguna combinación de valores de
  X que las satisfaga a la vez.
- `classification: compatible_indeterminado`: hay infinitas soluciones. Dos o más
  ecuaciones son linealmente dependientes (una fila de A es combinación de otras), así
  que el modelo está mal especificado y falta información para fijar una solución
  única. Di cuántos grados de libertad hay y que hace falta una condición adicional.
- Nunca acompañes un sistema singular con un resultado numérico inventado.

RESPUESTA FINAL
Redacta en español un análisis listo para convertirse en informe, con:
- el diagnóstico del sistema (det(A), rangos, clasificación) y su lectura en los
  términos del problema;
- los pasos intermedios de cada método que hayas ejecutado (operaciones de fila y
  despeje de cada variable), citando lo que devolvió el motor;
- el vector X solo si el motor lo entregó, etiquetando cada componente con el nombre
  que corresponda según el orden de prioridad de arriba;
- el resultado de la validación cruzada y del error de sustitución ‖AX-B‖;
- la conclusión: si el escenario es alcanzable o qué restricción lo bloquea.

FORMATO DE LA RESPUESTA FINAL
El texto se renderiza como Markdown (GitHub Flavored Markdown), en el frontend y en
los informes PDF/DOCX. Escribe solo el subconjunto que ambos entienden:
- encabezados con `##` y `###` para separar las secciones del análisis;
- `**texto**` para las negritas;
- tablas Markdown normales, con la fila de guiones `|---|`, para comparar métodos o
  etiquetar las componentes de X;
- listas con `-`.

No uses notación LaTeX: nada de `$$...$$`, `$...$` ni `\\begin{pmatrix}`. No hay
renderizador de fórmulas, así que ese texto aparecería roto. Para mostrar una matriz
o un vector, usa una tabla Markdown o un bloque de código con ``` y las columnas
alineadas con espacios.
"""

_SYSTEM_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "A": {
            "type": "array",
            "description": (
                "Matriz de coeficientes cuadrada nxn del sistema AX=B. Cada fila es "
                "una ecuación y cada columna la variable x1..xn que multiplica."
            ),
            "items": {"type": "array", "items": {"type": "number"}},
        },
        "B": {
            "type": "array",
            "description": (
                "Vector de términos independientes del sistema, con n elementos: el "
                "lado derecho de cada ecuación."
            ),
            "items": {"type": "number"},
        },
        "variable_names": {
            "type": "array",
            "description": (
                "Opcional. Nombres para las columnas de A (variables x1..xn), en ese "
                "orden, si el usuario los proporcionó. No los inventes."
            ),
            "items": {"type": "string"},
        },
    },
    "required": ["A", "B"],
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": TOOL_BUSCAR_CONOCIMIENTO,
        "description": (
            "Busca en la base de conocimiento indexada (notas de Obsidian) la "
            "terminología, las entidades y las unidades del problema planteado. Úsala "
            "para interpretar qué representa cada fila y cada columna del sistema, y "
            "descarta los fragmentos que no hablen de este problema. No devuelve "
            "cálculos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Consulta en lenguaje natural sobre el problema o su "
                        "terminología."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": f"Número de fragmentos a devolver (por defecto {DEFAULT_TOP_K}).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": TOOL_DIAGNOSTICAR_SISTEMA,
        "description": (
            "OBLIGATORIA antes de cualquier resolución. Calcula det(A), rango(A) y "
            "rango([A|B]) con aritmética exacta y clasifica el sistema como "
            "compatible_determinado, compatible_indeterminado o incompatible. Si "
            "devuelve is_singular=true, no intentes resolver el sistema."
        ),
        "input_schema": _SYSTEM_INPUT_SCHEMA,
    },
    {
        "name": TOOL_RESOLVER_GAUSS,
        "description": (
            "Resuelve AX=B por eliminación de Gauss (triangulación y sustitución hacia "
            "atrás) y devuelve el vector X con todas las operaciones de fila. Rechaza "
            "los sistemas singulares."
        ),
        "input_schema": _SYSTEM_INPUT_SCHEMA,
    },
    {
        "name": TOOL_RESOLVER_GAUSS_JORDAN,
        "description": (
            "Resuelve AX=B por Gauss-Jordan reduciendo [A|B] a [I|X] y devuelve el "
            "vector X con todas las operaciones de fila. Rechaza los sistemas "
            "singulares."
        ),
        "input_schema": _SYSTEM_INPUT_SCHEMA,
    },
    {
        "name": TOOL_RESOLVER_MATRIZ_INVERSA,
        "description": (
            "Resuelve AX=B calculando A^-1 y evaluando X = A^-1*B; devuelve la inversa, "
            "el vector X y los pasos. Rechaza los sistemas singulares. Al completarse "
            "los tres métodos, el resultado incluye `validacion_cruzada` con la "
            "comparación entre ellos, el error de sustitución y la factibilidad."
        ),
        "input_schema": _SYSTEM_INPUT_SCHEMA,
    },
]

_SOLVERS: dict[str, Callable[[LinearSystemInput], MethodSolution]] = {
    TOOL_RESOLVER_GAUSS: solve_gauss,
    TOOL_RESOLVER_GAUSS_JORDAN: solve_gauss_jordan,
    TOOL_RESOLVER_MATRIZ_INVERSA: solve_matrix_inverse,
}

RESOLUTION_TOOLS = frozenset(_SOLVERS)
PROTOCOL_DIAGNOSE_FIRST = (
    "Protocolo del agente: debes llamar primero a `diagnosticar_sistema` "
    "antes de cualquier herramienta de resolución."
)
PROTOCOL_DIAGNOSE_BEFORE_FINISH = (
    "Antes de concluir debes llamar a `diagnosticar_sistema`. "
    "No ofrezcas un análisis ni un vector X sin ese diagnóstico."
)
PROTOCOL_SOLVE_BEFORE_NUMBERS = (
    "No puedes presentar un resultado numérico sin haber llamado a las "
    "herramientas de resolución del motor (`resolver_por_gauss`, "
    "`resolver_por_gauss_jordan`, `resolver_por_matriz_inversa`)."
)
PROTOCOL_NO_X_WHEN_SINGULAR = (
    "El sistema es singular: no ofrezcas ningún vector solución. "
    "Explica el diagnóstico en lenguaje de negocio."
)

# X=(15,20,25) o x1=15: un modelo que "calcula" a mano.
_NUMERIC_VECTOR = re.compile(
    r"(?:X\s*=\s*)?(?:\[|\()?\s*-?\d+(?:[.,]\d+)?(?:\s*,\s*-?\d+(?:[.,]\d+)?){2,}\s*(?:\]|\))?",
    re.IGNORECASE,
)
_NAMED_COMPONENT = re.compile(r"\bx\s*[1-6]\s*=\s*-?\d", re.IGNORECASE)


class AgentError(Exception):
    """Fallo del orquestador que impide entregar un análisis."""


class MissingAnthropicKeyError(AgentError):
    """No hay credenciales para hablar con la API de Anthropic."""


class ToolInputError(Exception):
    """El modelo pasó argumentos que el motor no acepta; se le devuelve como error."""


def get_anthropic_client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise MissingAnthropicKeyError(
            "ANTHROPIC_API_KEY es obligatorio para orquestar el agente."
        )
    return Anthropic(api_key=settings.anthropic_api_key)


def _parse_system(payload: dict[str, Any]) -> LinearSystemInput:
    try:
        return LinearSystemInput(A=payload.get("A"), B=payload.get("B"))
    except ValidationError as exc:
        raise ToolInputError(
            "Los argumentos A y B no forman un sistema válido: "
            + "; ".join(error["msg"] for error in exc.errors())
        ) from exc


def _names(value: Any) -> list[str] | None:
    if isinstance(value, Sequence) and not isinstance(value, str):
        names = [str(item) for item in value]
        return names or None
    return None


class AgentRun:
    """Estado de una corrida: sistema en juego, métodos ya resueltos y traza de tools."""

    def __init__(self, request: AgentRunRequest, model: str) -> None:
        self.request = request
        self.model = model
        self.tools: list[ToolCallRecord] = []
        self.system: LinearSystemInput | None = None
        self.variable_names: list[str] | None = request.variable_names
        self.cross_validation = None
        self.substitution = None
        self.feasibility = None
        self._methods: dict[SolutionMethod, MethodSolution] = {}
        self._signature: tuple[Any, ...] | None = None

        if request.A is not None and request.B is not None:
            self.system = LinearSystemInput(A=request.A, B=request.B)

    # -- despacho de herramientas -------------------------------------------------

    def execute(self, name: str, payload: Any) -> tuple[Any, bool]:
        """Ejecuta una herramienta y devuelve (salida, is_error)."""
        if not isinstance(payload, dict):
            return {"error": "Los argumentos de la herramienta deben ser un objeto."}, True

        try:
            if name == TOOL_BUSCAR_CONOCIMIENTO:
                return self._buscar_conocimiento(payload), False
            if name == TOOL_DIAGNOSTICAR_SISTEMA:
                return self._diagnosticar_sistema(payload), False
            if name in _SOLVERS:
                return self._resolver(name, payload)
        except ToolInputError as exc:
            return {"error": str(exc)}, True

        return {"error": f"Herramienta desconocida: {name}"}, True

    def _buscar_conocimiento(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ToolInputError("`query` es obligatoria y debe ser texto no vacío.")

        top_k = payload.get("top_k", DEFAULT_TOP_K)
        if not isinstance(top_k, int) or isinstance(top_k, bool):
            top_k = DEFAULT_TOP_K

        hits = search_knowledge(query, top_k=top_k)
        return {
            "query": query,
            "resultados": [
                {
                    "contenido": hit.content,
                    "fuente": hit.metadata.get("obsidian_path"),
                    "titulo": hit.metadata.get("title"),
                    "similitud": hit.similarity,
                }
                for hit in hits
            ],
        }

    def _diagnosticar_sistema(self, payload: dict[str, Any]) -> dict[str, Any]:
        system = self._track(payload)
        diagnosis = validate_system(system)
        output = diagnosis.model_dump(mode="json")
        if diagnosis.is_singular:
            output["instruccion"] = (
                "Sistema singular: no llames a las herramientas de resolución. "
                "Explica el diagnóstico en lenguaje de negocio sin ofrecer ningún "
                "vector solución."
            )
        return output

    def _resolver(self, name: str, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        system = self._track(payload)

        # Guardrail: el diagnóstico corre aunque el modelo se lo haya saltado.
        diagnosis = validate_system(system)
        if diagnosis.is_singular:
            return {
                "error": (
                    "Sistema singular: el motor no resuelve ni devuelve un vector X. "
                    "Explica el diagnóstico en lenguaje de negocio."
                ),
                "diagnostico": diagnosis.model_dump(mode="json"),
            }, True

        try:
            solution = _SOLVERS[name](system)
        except SingularSystemError as exc:
            return {
                "error": f"El motor detuvo la resolución: {exc}",
                "diagnostico": diagnosis.model_dump(mode="json"),
            }, True

        self._methods[solution.method] = solution
        output: dict[str, Any] = {
            "metodo": solution.method.value,
            "diagnostico": diagnosis.model_dump(mode="json"),
            **solution.model_dump(mode="json", exclude={"method"}),
        }

        report = self._cross_validate(system)
        if report is not None:
            output["validacion_cruzada"] = report
        return output, False

    # -- estado compartido --------------------------------------------------------

    def _track(self, payload: dict[str, Any]) -> LinearSystemInput:
        """Registra el sistema que el modelo está usando y detecta cambios de dataset."""
        system = _parse_system(payload)
        names = _names(payload.get("variable_names"))
        if self.request.variable_names is None and names is not None:
            self.variable_names = names

        signature = (tuple(tuple(row) for row in system.A), tuple(system.B))
        if signature != self._signature:
            # El modelo pasó a otro sistema: los métodos anteriores ya no comparan.
            self._signature = signature
            self._methods = {}
            self.cross_validation = None
            self.substitution = None
            self.feasibility = None
        self.system = system
        return system

    def _cross_validate(self, system: LinearSystemInput) -> dict[str, Any] | None:
        """Compara los tres métodos en cuanto están los tres; el modelo no calcula nada."""
        if len(self._methods) < len(_SOLVERS):
            return None

        methods = [
            self._methods[method]
            for method in (
                SolutionMethod.GAUSS,
                SolutionMethod.GAUSS_JORDAN,
                SolutionMethod.MATRIX_INVERSE,
            )
        ]
        try:
            self.cross_validation = cross_validate_methods(system, methods)
        except MethodInconsistencyError as exc:
            return {
                "coincidencia": False,
                "error": str(exc),
                "desviacion_maxima": exc.max_deviation,
            }

        solution = self.cross_validation.solution
        self.substitution = verify_solution(system, solution)
        self.feasibility = check_feasibility(solution, self.variable_names)

        return {
            "coincidencia": True,
            "informe": self.cross_validation.model_dump(mode="json"),
            "sustitucion": self.substitution.model_dump(mode="json"),
            "factibilidad": self.feasibility.model_dump(mode="json"),
        }

    def trace(self, final_response: str) -> AgentRunTrace:
        return AgentRunTrace(
            A=self.system.A if self.system is not None else None,
            B=self.system.B if self.system is not None else None,
            variable_names=self.variable_names,
            resource_names=self.request.resource_names,
            tools=self.tools,
            cross_validation=self.cross_validation,
            substitution=self.substitution,
            feasibility=self.feasibility,
            final_response=final_response,
            model=self.model,
        )


def _initial_message(request: AgentRunRequest) -> str:
    parts = [f"Problema planteado por el usuario:\n{request.problem_text}"]

    if request.A is not None and request.B is not None:
        parts.append(
            "Sistema entregado ya estructurado (úsalo tal cual en las herramientas, "
            "no lo reescribas):\n"
            + json.dumps({"A": request.A, "B": request.B}, ensure_ascii=False)
        )
    else:
        parts.append(
            "No se entregó la matriz: extrae los coeficientes de A y los términos "
            "independientes de B del enunciado y pásalos a las herramientas. No "
            "resuelvas nada por tu cuenta."
        )

    if request.variable_names:
        parts.append(
            "Nombres de las columnas de A (variables x1..xn), en ese orden: "
            + json.dumps(request.variable_names, ensure_ascii=False)
        )
    if request.resource_names:
        parts.append(
            "Nombres de las filas de A (ecuaciones del sistema), en ese orden: "
            + json.dumps(request.resource_names, ensure_ascii=False)
        )

    return "\n\n".join(parts)


def _block_param(block: Any) -> dict[str, Any]:
    """Convierte un bloque de la respuesta en el parámetro equivalente del siguiente turno."""
    dump = getattr(block, "model_dump", None)
    if callable(dump):
        return dump(mode="json", exclude_none=True)

    kind = getattr(block, "type", None)
    if kind == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {"type": "text", "text": getattr(block, "text", "")}


def _final_text(blocks: Sequence[Any]) -> str:
    return "\n".join(
        block.text.strip()
        for block in blocks
        if getattr(block, "type", None) == "text" and getattr(block, "text", "").strip()
    )


def looks_like_numeric_solution(text: str) -> bool:
    """True si el texto parece un vector X o un despeje x1=… inventado por el modelo."""
    if _NAMED_COMPONENT.search(text):
        return True
    return _NUMERIC_VECTOR.search(text) is not None


def _successful_diagnosis(run: AgentRun) -> dict[str, Any] | None:
    for record in reversed(run.tools):
        if record.name == TOOL_DIAGNOSTICAR_SISTEMA and not record.is_error:
            return record.output if isinstance(record.output, dict) else None
    return None


def _has_resolved(run: AgentRun) -> bool:
    return any(
        record.name in RESOLUTION_TOOLS and not record.is_error for record in run.tools
    )


def protocol_reminder(run: AgentRun, final_text: str) -> str | None:
    """Si el modelo viola el protocolo, el texto a devolverle; None si la corrida es válida."""
    diagnosis = _successful_diagnosis(run)
    if diagnosis is None:
        return PROTOCOL_DIAGNOSE_BEFORE_FINISH

    is_singular = bool(diagnosis.get("is_singular"))
    numeric = looks_like_numeric_solution(final_text)

    if is_singular and numeric:
        return PROTOCOL_NO_X_WHEN_SINGULAR
    if not is_singular and numeric and not _has_resolved(run):
        return PROTOCOL_SOLVE_BEFORE_NUMBERS
    return None


def _persist(
    client: Client, request: AgentRunRequest, requested_by: UUID, trace: AgentRunTrace
) -> UUID:
    result = (
        client.table("estimations")
        .insert(
            {
                "problem_text": request.problem_text,
                "project_id": str(request.project_id),
                "requested_by": str(requested_by),
                "result_json": trace.model_dump(mode="json"),
            }
        )
        .execute()
    )
    if not result.data:
        raise AgentError("No se pudo registrar la estimación en Supabase.")
    estimation_id = UUID(str(result.data[0]["id"]))
    try:
        record_estimation_audit(
            client,
            employee_id=requested_by,
            project_id=request.project_id,
            estimation_id=estimation_id,
            tool_names=[record.name for record in trace.tools],
        )
    except AuditLogError as exc:
        raise AgentError(str(exc)) from exc
    return estimation_id


def run_agent(
    request: AgentRunRequest,
    requested_by: UUID,
    *,
    anthropic_client: Anthropic | None = None,
    supabase: Client | None = None,
) -> AgentRunResponse:
    """Corre el loop de tool use y registra el análisis final en `estimations`.

    El modelo decide el orden de las herramientas; este loop solo las ejecuta y le
    devuelve los resultados del motor hasta que entrega su análisis en texto.
    """
    llm = anthropic_client or get_anthropic_client()
    model = settings.anthropic_model
    run = AgentRun(request, model)

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": _initial_message(request)}
    ]
    final_response: str | None = None

    for _ in range(MAX_ROUNDS):
        response = llm.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        blocks = list(response.content)
        messages.append(
            {"role": "assistant", "content": [_block_param(block) for block in blocks]}
        )

        if response.stop_reason != "tool_use":
            candidate = _final_text(blocks)
            reminder = protocol_reminder(run, candidate)
            if reminder is not None:
                messages.append({"role": "user", "content": reminder})
                continue
            final_response = candidate
            break

        results: list[dict[str, Any]] = []
        for block in blocks:
            if getattr(block, "type", None) != "tool_use":
                continue
            diagnosed = _successful_diagnosis(run) is not None
            if block.name in RESOLUTION_TOOLS and not diagnosed:
                output, is_error = {"error": PROTOCOL_DIAGNOSE_FIRST}, True
            else:
                output, is_error = run.execute(block.name, block.input)
            run.tools.append(
                ToolCallRecord(
                    name=block.name,
                    input=block.input if isinstance(block.input, dict) else {},
                    output=output,
                    is_error=is_error,
                )
            )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output, ensure_ascii=False),
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": results})

    if final_response is None:
        raise AgentError(
            f"El agente agotó {MAX_ROUNDS} rondas de herramientas sin entregar un análisis."
        )

    trace = run.trace(final_response)
    client = supabase or get_supabase_client()
    estimation_id = _persist(client, request, requested_by, trace)

    return AgentRunResponse(
        estimation_id=estimation_id,
        final_response=final_response,
        result_json=trace,
    )
