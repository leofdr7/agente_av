"""Generación de informes DOCX/PDF a partir de un registro de `estimations`.

No resuelve AX=B: solo transcribe la traza ya persistida en `result_json`,
la convierte en documentos y los sube al bucket privado `reports`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import UUID
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from jinja2 import Environment, FileSystemLoader, select_autoescape
from supabase import Client

from app.core.config import settings
from app.models.agent import AgentRunTrace, ToolCallRecord
from app.models.linear_system import (
    SubstitutionCheck,
    SystemClassification,
    SystemDiagnosis,
)
from app.models.report import ReportFile, ReportGenerationResponse
from app.services.agent import (
    TOOL_DIAGNOSTICAR_SISTEMA,
    TOOL_RESOLVER_GAUSS,
    TOOL_RESOLVER_GAUSS_JORDAN,
    TOOL_RESOLVER_MATRIZ_INVERSA,
)
from app.services.linear_systems_engine import NEGATIVE_SOLUTION_COMPONENT
from app.services.markdown_blocks import (
    Block,
    CodeBlock,
    Heading,
    ListBlock,
    MarkdownParseError,
    Paragraph,
    Span,
    Table,
    looks_numeric,
    parse_markdown,
    spans_text,
)

_APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = _APP_DIR / "templates"
ASSETS_DIR = _APP_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

COMPANY = "AgentA"
NAVY = RGBColor(0x0F, 0x20, 0x40)
# Mismos acentos que el frontend: cobre para el resultado, acero para lo secundario.
COPPER = RGBColor(0xC4, 0x5C, 0x26)
STEEL = RGBColor(0x5B, 0x65, 0x75)
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"

METHOD_SPECS: tuple[tuple[str, str, str], ...] = (
    ("gauss", TOOL_RESOLVER_GAUSS, "Gauss"),
    ("gauss_jordan", TOOL_RESOLVER_GAUSS_JORDAN, "Gauss-Jordan"),
    ("matrix_inverse", TOOL_RESOLVER_MATRIZ_INVERSA, "Matriz inversa"),
)

# Los tres métodos aplican las mismas operaciones de fila (el pivoteo solo mira A),
# sobre matrices de trabajo distintas. Decirlo evita leerlos como pasos repetidos.
MATRIX_CAPTIONS: dict[str, str] = {
    "gauss": (
        "Matriz ampliada [A|B] triangulada por debajo del pivote; X sale por "
        "sustitución hacia atrás."
    ),
    "gauss_jordan": (
        "Matriz ampliada [A|B] reducida hasta [I|X]: la última columna termina "
        "siendo el vector solución."
    ),
    "matrix_inverse": (
        "Matriz ampliada [A|I] reducida hasta [I|A⁻¹]: el bloque derecho termina "
        "siendo la inversa."
    ),
}

CLASSIFICATION_LABELS = {
    SystemClassification.COMPATIBLE_DETERMINADO.value: "compatible determinado",
    SystemClassification.COMPATIBLE_INDETERMINADO.value: "compatible indeterminado",
    SystemClassification.INCOMPATIBLE.value: "incompatible",
}

NEGATIVE_COMPONENT_TEXT = (
    "componente de solución negativo: el vector solución tiene al menos un valor "
    "negativo, así que el escenario planteado no es realizable"
)


class ReportError(Exception):
    """Fallo al construir, subir o registrar un informe."""


class EstimationNotFoundError(ReportError):
    """No hay fila en `estimations` para el id pedido."""


class EstimationIncompleteError(ReportError):
    """La estimación existe pero aún no tiene `result_json`."""


class StorageUploadError(ReportError):
    """Supabase Storage rechazó la subida o la firma de URL."""


class WeasyPrintUnavailableError(ReportError):
    """Faltan Pango/Cairo u otra dependencia de sistema de WeasyPrint."""


@dataclass
class StepBlock:
    description: str
    matrix: list[list[float]]
    matrix_html: str


@dataclass
class MethodSection:
    key: str
    title: str
    ran: bool
    skip_reason: str | None
    matrix_caption: str
    step_blocks: list[StepBlock]
    component_steps: list[dict[str, Any]]
    solution: list[float] | None
    inverse_matrix: list[list[float]] | None
    inverse_html: str | None


@dataclass
class ComparisonRow:
    label: str
    values: list[str]


@dataclass
class ReportContext:
    estimation_id: UUID
    project_title: str
    problem_text: str
    generated_at: datetime
    company: str
    executive_blocks: list[Block]
    executive_html: str
    methods: list[MethodSection]
    method_titles: list[str]
    comparison_available: bool
    comparison_rows: list[ComparisonRow]
    methods_agree: bool
    comparison_verdict: str
    substitution: SubstitutionCheck | None
    diagnosis: SystemDiagnosis | None
    diagnosis_label: str
    conclusion_paragraphs: list[str]
    needs_alert: bool


def fmt_number(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.6g}"
    except (TypeError, ValueError):
        return str(value)


def mock_pdf_renderer(html: str) -> bytes:
    """Sustituto documentado de WeasyPrint cuando no hay Pango/Cairo.

    Produce bytes con cabecera PDF para poder ejercitar upload y persistencia
    en desarrollo local. No es un informe visual: hay que instalar las libs
    de sistema del README (o usar Docker) para un PDF real.
    """
    del html
    return (
        b"%PDF-1.4\n"
        b"% MOCK WeasyPrint: Pango/Cairo no disponible en este entorno.\n"
        b"%%EOF\n"
    )


def _weasyprint_write_pdf(html: str, base_url: str) -> bytes:
    from weasyprint import HTML

    pdf = HTML(string=html, base_url=base_url).write_pdf()
    if not pdf:
        raise WeasyPrintUnavailableError("WeasyPrint devolvió un PDF vacío.")
    return bytes(pdf)


def render_pdf(
    html: str, *, renderer: Callable[[str], bytes] | None = None
) -> bytes:
    """Renderiza el HTML a PDF con WeasyPrint, o con un renderer inyectado."""
    if renderer is not None:
        return renderer(html)
    try:
        return _weasyprint_write_pdf(html, str(ASSETS_DIR))
    except (ImportError, OSError) as exc:
        raise WeasyPrintUnavailableError(
            "WeasyPrint no puede generar PDF: faltan bibliotecas de sistema "
            "(Pango/Cairo). Instálalas según el README o ejecuta el backend en Docker."
        ) from exc


def _matrix_html(matrix: list[list[float]] | None, split: int | None = None) -> str:
    """Matriz como tabla; `split` dibuja la barra de ampliación tras esa columna."""
    if not matrix:
        return ""
    cols = max((len(row) for row in matrix), default=0)
    bar = split if split is not None and 0 < split < cols else None
    parts = ['<table class="matrix">']
    for row in matrix:
        parts.append("<tr>")
        padded = list(row) + [None] * (cols - len(row))
        for index, value in enumerate(padded):
            css = ' class="bar"' if index == bar else ""
            parts.append(f"<td{css}>{escape(fmt_number(value))}</td>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def _spans_html(spans: list[Span]) -> str:
    parts: list[str] = []
    for span in spans:
        text = escape(span.text)
        if span.bold:
            parts.append(f"<strong>{text}</strong>")
        elif span.code:
            parts.append(f"<code>{text}</code>")
        else:
            parts.append(text)
    return "".join(parts)


def markdown_html(blocks: list[Block]) -> str:
    """Escribe los bloques del resumen como HTML; el texto va escapado."""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, Heading):
            # El resumen vive bajo un h2 del informe: sus encabezados arrancan en h3.
            tag = f"h{min(block.level + 2, 6)}"
            parts.append(f"<{tag}>{_spans_html(block.spans)}</{tag}>")
        elif isinstance(block, Paragraph):
            parts.append(f"<p>{_spans_html(block.spans)}</p>")
        elif isinstance(block, ListBlock):
            tag = "ol" if block.ordered else "ul"
            items = "".join(f"<li>{_spans_html(item)}</li>" for item in block.items)
            parts.append(f"<{tag}>{items}</{tag}>")
        elif isinstance(block, CodeBlock):
            parts.append(f"<pre>{escape(block.text)}</pre>")
        elif isinstance(block, Table):
            parts.append(_table_html(block))
    return "".join(parts)


def _table_html(block: Table) -> str:
    parts = ["<table>", "<thead><tr>"]
    for cell in block.header:
        parts.append(f'<th class="label">{_spans_html(cell)}</th>')
    parts.append("</tr></thead><tbody>")
    for row in block.rows:
        parts.append("<tr>")
        for cell in row:
            css = "" if looks_numeric(cell) else ' class="label"'
            parts.append(f"<td{css}>{_spans_html(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _join_fmt(values: list[float] | None) -> str:
    if not values:
        return "—"
    return ", ".join(fmt_number(value) for value in values)


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["fmt"] = fmt_number
    env.filters["join_fmt"] = _join_fmt
    return env


def render_html(ctx: ReportContext) -> str:
    return _env().get_template("report.html").render(ctx=ctx)


def _set_run_font(run, *, size: int, bold: bool = False, color: RGBColor | None = None) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color or NAVY
    run.font.name = "Calibri"
    r_pr = getattr(run._element, "rPr", None)
    if r_pr is not None and r_pr.rFonts is not None:
        r_pr.rFonts.set(qn("w:eastAsia"), "Calibri")


def _set_cell_borders(cell, *, bar: bool) -> None:
    """Borde de grilla; `bar` engrosa el lado izquierdo, la barra de ampliación."""
    borders = OxmlElement("w:tcBorders")
    for edge, size, color in (
        ("top", "4", "C5CED9"),
        ("left", "16" if bar else "4", "5B6575" if bar else "C5CED9"),
        ("bottom", "4", "C5CED9"),
        ("right", "4", "C5CED9"),
    ):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)
        borders.append(element)
    cell._tc.get_or_add_tcPr().append(borders)


def _add_matrix_table(
    document: Document, matrix: list[list[float]], split: int | None = None
) -> None:
    """Tabla de la matriz de trabajo. `split` marca la primera columna ampliada."""
    cols = len(matrix[0])
    bar = split if split is not None and 0 < split < cols else None
    table = document.add_table(rows=len(matrix), cols=cols)
    table.style = "Table Grid"
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            cell = table.rows[i].cells[j]
            cell.text = fmt_number(value)
            _set_cell_borders(cell, bar=j == bar)
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                for run in paragraph.runs:
                    run.font.size = Pt(8)
                    run.font.name = "Calibri"


def _add_spans(paragraph, spans: list[Span], *, size: int = 10) -> None:
    for span in spans:
        run = paragraph.add_run(span.text)
        _set_run_font(run, size=size, bold=span.bold)
        if span.code:
            run.font.name = "Consolas"


def _add_markdown_table(document: Document, block: Table) -> None:
    cols = max([len(block.header), *(len(row) for row in block.rows)] or [0])
    if not cols:
        return
    table = document.add_table(rows=1 + len(block.rows), cols=cols)
    table.style = "Table Grid"
    for index, cell in enumerate(block.header[:cols]):
        target = table.rows[0].cells[index]
        target.text = ""
        _add_spans(target.paragraphs[0], [Span(spans_text(cell), bold=True)], size=9)
    for i, row in enumerate(block.rows, start=1):
        for j, cell in enumerate(row[:cols]):
            target = table.rows[i].cells[j]
            target.text = ""
            paragraph = target.paragraphs[0]
            if looks_numeric(cell):
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            _add_spans(paragraph, cell, size=9)


def _add_markdown_blocks(document: Document, blocks: list[Block]) -> None:
    """Escribe el resumen del agente con formato de Word, no con los símbolos."""
    for block in blocks:
        if isinstance(block, Heading):
            # El resumen es una sección de nivel 1; sus encabezados van debajo.
            heading = document.add_heading(level=min(block.level + 1, 4))
            _add_spans(heading, block.spans, size=12)
        elif isinstance(block, Paragraph):
            _add_spans(document.add_paragraph(), block.spans)
        elif isinstance(block, ListBlock):
            style = "List Number" if block.ordered else "List Bullet"
            for item in block.items:
                _add_spans(document.add_paragraph(style=style), item)
        elif isinstance(block, CodeBlock):
            paragraph = document.add_paragraph()
            run = paragraph.add_run(block.text)
            _set_run_font(run, size=9)
            run.font.name = "Consolas"
        elif isinstance(block, Table):
            _add_markdown_table(document, block)


def render_docx(ctx: ReportContext) -> bytes:
    document = Document()
    section = document.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    if LOGO_PATH.exists():
        paragraph.add_run().add_picture(str(LOGO_PATH), width=Inches(0.52))
        paragraph.add_run("  ")
    brand = paragraph.add_run(f"{ctx.company}  ·  Informe de estimación")
    _set_run_font(brand, size=10, bold=True)
    date_run = paragraph.add_run(
        f"\n{ctx.generated_at.strftime('%Y-%m-%d %H:%M UTC')}  ·  {ctx.estimation_id}"
    )
    _set_run_font(date_run, size=8, color=STEEL)

    title = document.add_heading(ctx.project_title, level=0)
    for run in title.runs:
        _set_run_font(run, size=22, bold=True)
    intro = document.add_paragraph(f"Enunciado: {ctx.problem_text}")
    for run in intro.runs:
        _set_run_font(run, size=10, color=STEEL)

    document.add_heading("Resumen ejecutivo", level=1)
    _add_markdown_blocks(document, ctx.executive_blocks)

    document.add_heading("Resolución multimétodo", level=1)
    document.add_paragraph(
        "Cada subsección reproduce la traza analítica registrada por el motor "
        "(operaciones elementales de fila y, cuando aplica, el despeje de cada "
        "componente de X). No se recalcula nada en este informe."
    )
    for method in ctx.methods:
        document.add_heading(method.title, level=2)
        if not method.ran:
            document.add_paragraph(method.skip_reason or "Este método no se ejecutó.")
            continue
        if method.solution:
            result = document.add_paragraph()
            label = result.add_run("Vector solución  ")
            _set_run_font(label, size=10, bold=True, color=COPPER)
            value = result.add_run(f"X = ({_join_fmt(method.solution)})")
            _set_run_font(value, size=10)
        if method.matrix_caption:
            caption = document.add_paragraph(method.matrix_caption)
            for run in caption.runs:
                _set_run_font(run, size=9, color=STEEL)
        split = len(method.solution) if method.solution else None
        for index, step in enumerate(method.step_blocks, start=1):
            operation = document.add_paragraph()
            number = operation.add_run(f"{index:02d}  ")
            _set_run_font(number, size=9, color=STEEL)
            symbolic = operation.add_run(step.description)
            _set_run_font(symbolic, size=10, bold=True)
            if step.matrix:
                _add_matrix_table(document, step.matrix, split)
            document.add_paragraph()
        if method.inverse_matrix:
            document.add_paragraph("Matriz inversa A⁻¹:")
            _add_matrix_table(document, method.inverse_matrix)
        if method.component_steps:
            document.add_paragraph("Despeje de las componentes de X:")
            for item in method.component_steps:
                document.add_paragraph(
                    f"{item['equation']} = {fmt_number(item['value'])}",
                    style="List Bullet",
                )

    document.add_heading("Tabla comparativa", level=1)
    if ctx.comparison_available and ctx.comparison_rows:
        table = document.add_table(
            rows=1 + len(ctx.comparison_rows), cols=1 + len(ctx.method_titles)
        )
        table.style = "Table Grid"
        headers = ["Variable", *ctx.method_titles]
        for j, label in enumerate(headers):
            table.rows[0].cells[j].text = label
        for i, row in enumerate(ctx.comparison_rows, start=1):
            table.rows[i].cells[0].text = row.label
            for j, value in enumerate(row.values):
                table.rows[i].cells[j + 1].text = value
    document.add_paragraph(ctx.comparison_verdict)

    document.add_heading("Verificación de sustitución directa", level=1)
    if ctx.substitution:
        status = (
            "El residual queda dentro de tolerancia."
            if ctx.substitution.within_tolerance
            else "El residual no queda dentro de tolerancia."
        )
        document.add_paragraph(
            f"E = |AX − B| = {fmt_number(ctx.substitution.error_norm)} "
            f"(tolerancia {fmt_number(ctx.substitution.tolerance)}). {status}"
        )
    else:
        document.add_paragraph(
            "No hay verificación de sustitución: el motor no entregó un vector X."
        )

    document.add_heading("Diagnóstico y conclusiones", level=1)
    if ctx.diagnosis:
        singular = " Sistema singular." if ctx.diagnosis.is_singular else ""
        document.add_paragraph(
            f"Clasificación: {ctx.diagnosis_label}. "
            f"det(A) = {fmt_number(ctx.diagnosis.determinant)}, "
            f"rango(A) = {ctx.diagnosis.rank_a}, "
            f"rango([A|B]) = {ctx.diagnosis.rank_augmented}.{singular}"
        )
        document.add_paragraph(ctx.diagnosis.message)
    for para in ctx.conclusion_paragraphs:
        document.add_paragraph(para)

    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _last_tool(trace: AgentRunTrace, name: str) -> ToolCallRecord | None:
    for record in reversed(trace.tools):
        if record.name == name:
            return record
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _method_section(trace: AgentRunTrace, key: str, tool_name: str, title: str) -> MethodSection:
    record = _last_tool(trace, tool_name)
    diagnosis = _extract_diagnosis(trace)
    singular = diagnosis.is_singular if diagnosis is not None else False

    if record is None:
        reason = (
            "Sistema singular: el motor no ejecutó este método ni entregó un vector X."
            if singular
            else "Este método no se ejecutó en la estimación."
        )
        return MethodSection(
            key=key,
            title=title,
            ran=False,
            skip_reason=reason,
            matrix_caption="",
            step_blocks=[],
            component_steps=[],
            solution=None,
            inverse_matrix=None,
            inverse_html=None,
        )

    output = _as_dict(record.output)
    if record.is_error:
        reason = str(
            output.get("error")
            or "El motor detuvo la resolución de este método."
        )
        return MethodSection(
            key=key,
            title=title,
            ran=False,
            skip_reason=reason,
            matrix_caption="",
            step_blocks=[],
            component_steps=[],
            solution=None,
            inverse_matrix=None,
            inverse_html=None,
        )

    steps = output.get("steps") or []
    solution = output.get("solution")
    # La barra de ampliación separa A de lo que se arrastra a su derecha: B en
    # Gauss y Gauss-Jordan, la identidad que se vuelve A⁻¹ en el tercer método.
    split = len(solution) if isinstance(solution, list) else None
    step_blocks = [
        StepBlock(
            description=str(step.get("description", "")),
            matrix=list(step.get("matrix_state") or []),
            matrix_html=_matrix_html(step.get("matrix_state"), split),
        )
        for step in steps
        if isinstance(step, dict)
    ]
    inverse = output.get("inverse_matrix")
    components = output.get("component_steps") or []
    return MethodSection(
        key=key,
        title=title,
        ran=True,
        skip_reason=None,
        matrix_caption=MATRIX_CAPTIONS.get(key, ""),
        step_blocks=step_blocks,
        component_steps=[item for item in components if isinstance(item, dict)],
        solution=list(solution) if isinstance(solution, list) else None,
        inverse_matrix=list(inverse) if isinstance(inverse, list) else None,
        inverse_html=_matrix_html(inverse) if isinstance(inverse, list) else None,
    )


def _extract_diagnosis(trace: AgentRunTrace) -> SystemDiagnosis | None:
    record = _last_tool(trace, TOOL_DIAGNOSTICAR_SISTEMA)
    payload: Any = None
    if record is not None:
        payload = _as_dict(record.output)
        payload.pop("instruccion", None)
    if not payload:
        for spec in METHOD_SPECS:
            solver = _last_tool(trace, spec[1])
            if solver is None:
                continue
            output = _as_dict(solver.output)
            payload = output.get("diagnostico")
            if payload:
                break
    if not payload:
        return None
    try:
        return SystemDiagnosis.model_validate(payload)
    except Exception:
        return None


def _project_title(row: dict[str, Any]) -> str:
    project = row.get("projects") or {}
    if isinstance(project, list) and project:
        project = project[0]
    name = project.get("name") if isinstance(project, dict) else None
    if isinstance(name, str) and name.strip():
        return name.strip()
    text = (row.get("problem_text") or "").strip()
    if len(text) > 80:
        return text[:77] + "..."
    return text or "Estimación sin título"


def _executive_blocks(text: str, fallback: str) -> list[Block]:
    """Resumen del agente ya interpretado; si no dejó nada, un párrafo de aviso."""
    try:
        blocks = parse_markdown(text) if text.strip() else []
    except MarkdownParseError as exc:
        raise ReportError(str(exc)) from exc
    return blocks or [Paragraph(spans=[Span(fallback)])]


def _variable_label(trace: AgentRunTrace, index: int) -> str:
    names = trace.variable_names or []
    if index < len(names) and names[index]:
        return f"{names[index]} (x{index + 1})"
    return f"x{index + 1}"


def _comparison(
    trace: AgentRunTrace, methods: list[MethodSection]
) -> tuple[bool, list[ComparisonRow], bool, str]:
    ran = [method for method in methods if method.ran and method.solution]
    if len(ran) < 3:
        return False, [], False, (
            "No hay tabla comparativa: los tres métodos no llegaron a un vector X "
            "(sistema singular, infactible de resolver, o corrida incompleta)."
        )

    size = max(len(method.solution or []) for method in ran)
    rows: list[ComparisonRow] = []
    for index in range(size):
        values = []
        for method in methods:
            if method.solution and index < len(method.solution):
                values.append(fmt_number(method.solution[index]))
            else:
                values.append("—")
        rows.append(ComparisonRow(label=_variable_label(trace, index), values=values))

    report = trace.cross_validation
    if report is None:
        # Si el agente no copió el informe, se infiere igualdad a la tolerancia del motor.
        vectors = [method.solution or [] for method in ran]
        max_dev = 0.0
        for i in range(size):
            column = [vector[i] for vector in vectors if i < len(vector)]
            max_dev = max(max_dev, max(column) - min(column))
        agreed = max_dev <= 1e-6
        verdict = (
            "Los tres métodos coinciden en el mismo vector solución X."
            if agreed
            else f"Los tres métodos no coinciden (desviación máxima {fmt_number(max_dev)})."
        )
        return True, rows, agreed, verdict

    agreed = report.passed
    verdict = (
        "Los tres métodos coinciden en el mismo vector solución X "
        f"(desviación máxima {fmt_number(report.max_deviation)}, "
        f"tolerancia {fmt_number(report.tolerance)})."
        if agreed
        else (
            "Los tres métodos no coinciden en X "
            f"(desviación máxima {fmt_number(report.max_deviation)}, "
            f"tolerancia {fmt_number(report.tolerance)})."
        )
    )
    return True, rows, agreed, verdict


def _conclusions(
    trace: AgentRunTrace,
    diagnosis: SystemDiagnosis | None,
    methods_agree: bool,
) -> tuple[list[str], bool]:
    paragraphs: list[str] = []
    alert = False

    if diagnosis is not None and diagnosis.is_singular:
        alert = True
        label = CLASSIFICATION_LABELS.get(diagnosis.classification.value, diagnosis.classification.value)
        paragraphs.append(
            "Alerta de sistema singular: el diagnóstico clasifica el sistema como "
            f"{label}. No existe un único plan de asignación que satisfaga las "
            "condiciones declaradas; el motor no entregó un vector X y este informe "
            "no debe leerse como una solución del sistema."
        )

    feasibility = trace.feasibility
    if feasibility is not None and feasibility.infeasible:
        alert = True
        reason = feasibility.reason_code or NEGATIVE_SOLUTION_COMPONENT
        if reason == NEGATIVE_SOLUTION_COMPONENT:
            reason_text = NEGATIVE_COMPONENT_TEXT
        else:
            reason_text = reason
        details = []
        for component in feasibility.components:
            name = component.label or component.variable
            details.append(f"{name} = {fmt_number(component.value)}")
        extra = f" Componentes afectadas: {'; '.join(details)}." if details else ""
        paragraphs.append(
            "Flag de infactibilidad traducido a lenguaje de negocio: "
            f"{reason_text}.{extra}"
        )

    if not paragraphs:
        if methods_agree and trace.substitution and trace.substitution.within_tolerance:
            paragraphs.append(
                "Los tres métodos coinciden en el mismo vector solución y la "
                "verificación de sustitución directa queda dentro de tolerancia. "
                "El plan de asignación es matemáticamente coherente y factible."
            )
        elif methods_agree:
            paragraphs.append(
                "Los tres métodos coinciden en el mismo vector solución X."
            )
        else:
            paragraphs.append(
                "Revisar la traza del motor: no hay un veredicto único sobre la "
                "solución del sistema."
            )

    return paragraphs, alert


def build_report_context(row: dict[str, Any], *, generated_at: datetime | None = None) -> ReportContext:
    """Arma el contexto del informe a partir del registro completo de `estimations`."""
    raw = row.get("result_json")
    if not raw:
        raise EstimationIncompleteError(
            "La estimación aún no tiene resultado: no se puede generar el informe."
        )
    trace = AgentRunTrace.model_validate(raw)
    generated = generated_at or datetime.now(timezone.utc)
    methods = [
        _method_section(trace, key, tool, title) for key, tool, title in METHOD_SPECS
    ]
    diagnosis = _extract_diagnosis(trace)
    available, rows, agreed, verdict = _comparison(trace, methods)
    conclusions, alert = _conclusions(trace, diagnosis, agreed)
    executive = _executive_blocks(
        trace.final_response,
        "El agente no dejó un resumen ejecutivo en esta estimación.",
    )
    diagnosis_label = ""
    if diagnosis is not None:
        diagnosis_label = CLASSIFICATION_LABELS.get(
            diagnosis.classification.value, diagnosis.classification.value
        )

    return ReportContext(
        estimation_id=UUID(str(row["id"])),
        project_title=_project_title(row),
        problem_text=str(row.get("problem_text") or ""),
        generated_at=generated,
        company=COMPANY,
        executive_blocks=executive,
        executive_html=markdown_html(executive),
        methods=methods,
        method_titles=[spec[2] for spec in METHOD_SPECS],
        comparison_available=available,
        comparison_rows=rows,
        methods_agree=agreed,
        comparison_verdict=verdict,
        substitution=trace.substitution,
        diagnosis=diagnosis,
        diagnosis_label=diagnosis_label,
        conclusion_paragraphs=conclusions,
        needs_alert=alert,
    )


def _load_estimation(client: Client, estimation_id: UUID) -> dict[str, Any]:
    result = (
        client.table("estimations")
        .select(
            "id, problem_text, result_json, project_id, requested_by, created_at, "
            "projects(name)"
        )
        .eq("id", str(estimation_id))
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        raise EstimationNotFoundError(
            f"No existe la estimación {estimation_id}."
        )
    return rows[0]


def _signed_url(response: Any) -> str:
    if isinstance(response, dict):
        url = response.get("signedURL") or response.get("signedUrl")
    else:
        url = getattr(response, "signedURL", None) or getattr(response, "signedUrl", None)
    if not url:
        raise StorageUploadError("Storage no devolvió una URL firmada.")
    return str(url)


def _sign_file(client: Client, path: str, download_name: str) -> str:
    try:
        signed = client.storage.from_(settings.reports_bucket).create_signed_url(
            path,
            settings.reports_signed_url_ttl_seconds,
            options={"download": download_name},
        )
    except Exception as exc:
        raise StorageUploadError(
            f"No se pudo firmar '{path}' en el bucket '{settings.reports_bucket}': {exc}"
        ) from exc
    return _signed_url(signed)


def _upload_file(
    client: Client,
    *,
    path: str,
    payload: bytes,
    content_type: str,
    download_name: str,
) -> str:
    try:
        client.storage.from_(settings.reports_bucket).upload(
            path,
            payload,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:
        raise StorageUploadError(
            f"No se pudo subir '{path}' al bucket '{settings.reports_bucket}': {exc}"
        ) from exc
    return _sign_file(client, path, download_name)


def generate_reports(
    estimation_id: UUID,
    client: Client,
    *,
    pdf_renderer: Callable[[str], bytes] | None = None,
) -> ReportGenerationResponse:
    """Genera DOCX y PDF, los sube a Storage y registra las filas en `reports`."""
    row = _load_estimation(client, estimation_id)
    generated_at = datetime.now(timezone.utc)
    ctx = build_report_context(row, generated_at=generated_at)
    html = render_html(ctx)
    documents: list[tuple[Literal["docx", "pdf"], str, bytes, str]] = [
        ("docx", DOCX_MIME, render_docx(ctx), "informe.docx"),
        ("pdf", PDF_MIME, render_pdf(html, renderer=pdf_renderer), "informe.pdf"),
    ]

    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    persisted: list[dict[str, Any]] = []
    stored_paths: dict[str, tuple[str, str]] = {}
    for file_type, mime, payload, filename in documents:
        path = f"{estimation_id}/{stamp}/{filename}"
        url = _upload_file(
            client,
            path=path,
            payload=payload,
            content_type=mime,
            download_name=filename,
        )
        stored_paths[file_type] = (path, filename)
        persisted.append(
            {
                "estimation_id": str(estimation_id),
                "file_url": url,
                "file_type": file_type,
                "generated_at": generated_at.isoformat(),
            }
        )

    try:
        inserted = client.table("reports").insert(persisted).execute()
    except Exception as exc:
        raise StorageUploadError(
            f"Los archivos se subieron pero no se pudieron registrar en `reports`: {exc}"
        ) from exc

    rows = list(inserted.data or [])
    if len(rows) != 2:
        raise ReportError(
            "Storage recibió los archivos pero `reports` no devolvió las dos filas insertadas."
        )

    # URL persistida = firma al subir; la respuesta se vuelve a firmar para no nacer caducada.
    reports: list[ReportFile] = []
    for item in rows:
        file_type = item["file_type"]
        path, filename = stored_paths[file_type]
        reports.append(
            ReportFile(
                id=item["id"],
                file_url=_sign_file(client, path, filename),
                file_type=file_type,
                generated_at=item["generated_at"],
            )
        )
    reports.sort(key=lambda item: 0 if item.file_type == "docx" else 1)
    return ReportGenerationResponse(estimation_id=estimation_id, reports=reports)
