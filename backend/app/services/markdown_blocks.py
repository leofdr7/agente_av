"""Lector del subconjunto de Markdown que el agente redacta en `final_response`.

El system prompt fija ese subconjunto: encabezados `#`, negritas `**texto**`,
código entre acentos, listas, tablas GFM y bloques ```. Devuelve bloques neutros
para que cada informe (DOCX o HTML) los escriba con su propio formato, en vez de
imprimir los símbolos literales.

No se admiten cursivas con un solo `*`: las operaciones del motor traen productos
como `(0.5)*F1` y un par suelto de asteriscos las partiría por la mitad.

El plazo no se impone con SIGALRM. El endpoint del informe corre en un hilo de
AnyIO, y esa señal solo se entrega al hilo principal del proceso. El lector se
detiene solo, con un contador de pasos y un plazo de reloj.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_FENCE = re.compile(r"^\s*```")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_INLINE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")
_NUMERIC = re.compile(r"^[-+]?[\d.,]+(?:[eE][-+]?\d+)?$")

# Tope duro: un resumen mal formado debe fallar enseguida, no comerse la RAM.
# No usa SIGALRM. POST /api/v1/estimations/{id}/report es una función síncrona y
# Starlette la ejecuta en un hilo de AnyIO, donde signal.alarm no se entrega.
# El corte es un contador de pasos más un plazo por reloj, ambos locales al hilo.
PARSE_TIMEOUT_SECONDS = 1
_DEBUG_LOG = Path("/home/leofdr7/Projects/Agente_algebra_vectorial/.cursor/debug-6e8e27.log")


@dataclass(frozen=True)
class Span:
    """Un tramo de texto en línea con su marca de formato."""

    text: str
    bold: bool = False
    code: bool = False


@dataclass(frozen=True)
class Heading:
    level: int
    spans: list[Span]


@dataclass(frozen=True)
class Paragraph:
    spans: list[Span]


@dataclass(frozen=True)
class ListBlock:
    ordered: bool
    items: list[list[Span]]


@dataclass(frozen=True)
class Table:
    header: list[list[Span]]
    rows: list[list[list[Span]]] = field(default_factory=list)


@dataclass(frozen=True)
class CodeBlock:
    text: str


Block = Heading | Paragraph | ListBlock | Table | CodeBlock


class MarkdownParseError(Exception):
    """El resumen no se pudo leer dentro del presupuesto de tiempo o de pasos."""


def _agent_log(message: str, data: dict[str, object]) -> None:
    # #region agent log
    try:
        _DEBUG_LOG.open("a").write(
            json.dumps(
                {
                    "sessionId": "6e8e27",
                    "runId": "post-fix",
                    "hypothesisId": "H1",
                    "location": "markdown_blocks.py:parse_markdown",
                    "message": message,
                    "data": data,
                    "timestamp": int(time.time() * 1000),
                }
            )
            + "\n"
        )
    except Exception:
        pass
    # #endregion


class _Budget:
    """Corta el lector por pasos o por reloj, en cualquier hilo."""

    def __init__(self, line_count: int) -> None:
        self.deadline = time.monotonic() + PARSE_TIMEOUT_SECONDS
        self.steps = 0
        # Varias pasadas por línea (bloque, tabla, lista). Sigue siendo O(n).
        self.limit = line_count * 8 + 8

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.limit or time.monotonic() > self.deadline:
            raise MarkdownParseError(
                "No se pudo interpretar el resumen: parse_markdown superó "
                f"{PARSE_TIMEOUT_SECONDS} s y se detuvo."
            )


def parse_markdown(text: str) -> list[Block]:
    """Convierte el Markdown del agente en bloques; el texto plano cae en párrafos.

    Una línea con `|` solo abre una tabla si la siguiente es el separador GFM
    (`---`). Cualquier otro `|` suelto es prosa. Si el lector deja de avanzar,
    o se pasa del presupuesto de pasos, lanza `MarkdownParseError`.
    """
    is_main = threading.current_thread() is threading.main_thread()
    _agent_log(
        "step budget armed",
        {
            "isMain": is_main,
            "thread": threading.current_thread().name,
            "alarmInstalled": False,
        },
    )
    return _parse_lines(text)


def _parse_lines(text: str) -> list[Block]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    budget = _Budget(len(lines))
    blocks: list[Block] = []
    index = 0

    while index < len(lines):
        budget.tick()
        previous = index
        line = lines[index]

        if not line.strip() or _RULE.match(line):
            index += 1
        elif _FENCE.match(line):
            body: list[str] = []
            index += 1
            while index < len(lines) and not _FENCE.match(lines[index]):
                budget.tick()
                body.append(lines[index])
                index += 1
            index += 1  # cierre del bloque (o fin del texto)
            blocks.append(CodeBlock("\n".join(body).strip("\n")))
        elif heading := _HEADING.match(line):
            blocks.append(
                Heading(len(heading.group(1)), parse_spans(heading.group(2).strip()))
            )
            index += 1
        elif _starts_table(lines, index):
            table, index = _read_table(lines, index, budget)
            blocks.append(table)
        elif _BULLET.match(line) or _ORDERED.match(line):
            block, index = _read_list(lines, index, budget)
            blocks.append(block)
        else:
            chunk: list[str] = []
            while index < len(lines) and _is_paragraph_line(lines, index):
                budget.tick()
                chunk.append(lines[index].strip())
                index += 1
            if chunk:
                blocks.append(Paragraph(parse_spans(" ".join(chunk))))

        if index <= previous:
            raise MarkdownParseError(
                "No se pudo interpretar el resumen: el lector no avanzó de línea "
                "y se detuvo."
            )

    return blocks


def parse_spans(text: str) -> list[Span]:
    """Parte una línea en tramos normal, negrita y código."""
    spans: list[Span] = []
    cursor = 0
    for match in _INLINE.finditer(text):
        if match.start() > cursor:
            spans.append(Span(text[cursor : match.start()]))
        if match.group(1) is not None:
            spans.append(Span(match.group(1), bold=True))
        else:
            spans.append(Span(match.group(2), code=True))
        cursor = match.end()
    if cursor < len(text):
        spans.append(Span(text[cursor:]))
    return [span for span in spans if span.text]


def spans_text(spans: list[Span]) -> str:
    return "".join(span.text for span in spans)


def looks_numeric(spans: list[Span]) -> bool:
    """Una celda que solo trae un número se alinea a la derecha en el informe."""
    text = spans_text(spans).strip()
    return bool(text) and bool(_NUMERIC.match(text))


def _split_raw(line: str) -> list[str]:
    """Celdas de una fila, sin regex. Conserva el texto interior de cada celda."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_cell(cell: str) -> bool:
    """Una celda GFM de separador es guiones, con `:` opcional en los extremos."""
    if not cell or "-" not in cell:
        return False
    body = cell
    if body.startswith(":"):
        body = body[1:]
    if body.endswith(":"):
        body = body[:-1]
    return bool(body) and all(char == "-" for char in body)


def _is_separator_row(line: str) -> bool:
    """Fila `---` de una tabla. Se recorre celda a celda; no hay cuantificadores anidados."""
    if "|" not in line or "-" not in line:
        return False
    cells = _split_raw(line)
    return bool(cells) and all(_is_separator_cell(cell) for cell in cells)


def _starts_table(lines: list[str], index: int) -> bool:
    """Cabecera con `|`, separador `---` y el mismo número de columnas."""
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    if not _is_separator_row(lines[index + 1]):
        return False
    header = _split_raw(lines[index])
    separator = _split_raw(lines[index + 1])
    return len(header) == len(separator) and len(header) >= 1


def _is_data_row(line: str, columns: int) -> bool:
    """Fila de datos solo si está alineada con la cabecera. Un `|` suelto no cuenta."""
    if not line.strip() or "|" not in line:
        return False
    if (
        _HEADING.match(line)
        or _FENCE.match(line)
        or _BULLET.match(line)
        or _ORDERED.match(line)
        or _is_separator_row(line)
    ):
        return False
    return len(_split_raw(line)) == columns


def _is_paragraph_line(lines: list[str], index: int) -> bool:
    line = lines[index]
    if not line.strip() or _RULE.match(line):
        return False
    if (
        _HEADING.match(line)
        or _FENCE.match(line)
        or _BULLET.match(line)
        or _ORDERED.match(line)
        or _starts_table(lines, index)
    ):
        return False
    return True


def _split_row(line: str) -> list[list[Span]]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [parse_spans(cell.strip()) for cell in stripped.split("|")]


def _read_table(lines: list[str], index: int, budget: _Budget) -> tuple[Table, int]:
    columns = len(_split_raw(lines[index]))
    header = _split_row(lines[index])
    index += 2  # encabezado y fila de guiones
    rows: list[list[list[Span]]] = []
    while index < len(lines) and _is_data_row(lines[index], columns):
        budget.tick()
        rows.append(_split_row(lines[index]))
        index += 1
    return Table(header=header, rows=rows), index


def _read_list(lines: list[str], index: int, budget: _Budget) -> tuple[ListBlock, int]:
    ordered = _ORDERED.match(lines[index]) is not None
    pattern = _ORDERED if ordered else _BULLET
    items: list[list[Span]] = []
    while index < len(lines):
        match = pattern.match(lines[index])
        if not match:
            break
        budget.tick()
        items.append(parse_spans(match.group(1).strip()))
        index += 1
    return ListBlock(ordered=ordered, items=items), index
