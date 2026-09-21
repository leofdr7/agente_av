"""Lector del subconjunto de Markdown que el agente redacta en `final_response`.

El system prompt fija ese subconjunto: encabezados `#`, negritas `**texto**`,
código entre acentos, listas, tablas GFM y bloques ```. Devuelve bloques neutros
para que cada informe (DOCX o HTML) los escriba con su propio formato, en vez de
imprimir los símbolos literales.

No se admiten cursivas con un solo `*`: las operaciones del motor traen productos
como `(0.5)*F1` y un par suelto de asteriscos las partiría por la mitad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_FENCE = re.compile(r"^\s*```")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")
_INLINE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")
_NUMERIC = re.compile(r"^[-+]?[\d.,]+(?:[eE][-+]?\d+)?$")


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


def parse_markdown(text: str) -> list[Block]:
    """Convierte el Markdown del agente en bloques; el texto plano cae en párrafos."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[Block] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if not line.strip() or _RULE.match(line):
            index += 1
            continue

        if _FENCE.match(line):
            body: list[str] = []
            index += 1
            while index < len(lines) and not _FENCE.match(lines[index]):
                body.append(lines[index])
                index += 1
            index += 1  # cierre del bloque (o fin del texto)
            blocks.append(CodeBlock("\n".join(body).strip("\n")))
            continue

        heading = _HEADING.match(line)
        if heading:
            blocks.append(
                Heading(len(heading.group(1)), parse_spans(heading.group(2).strip()))
            )
            index += 1
            continue

        if "|" in line and index + 1 < len(lines) and _is_divider(lines[index + 1]):
            table, index = _read_table(lines, index)
            blocks.append(table)
            continue

        if _BULLET.match(line) or _ORDERED.match(line):
            block, index = _read_list(lines, index)
            blocks.append(block)
            continue

        chunk: list[str] = []
        while index < len(lines) and _is_paragraph_line(lines[index]):
            chunk.append(lines[index].strip())
            index += 1
        blocks.append(Paragraph(parse_spans(" ".join(chunk))))

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


def _is_divider(line: str) -> bool:
    return "|" in line and bool(_TABLE_DIVIDER.match(line))


def _is_paragraph_line(line: str) -> bool:
    if not line.strip() or _RULE.match(line):
        return False
    return not (
        _HEADING.match(line)
        or _FENCE.match(line)
        or _BULLET.match(line)
        or _ORDERED.match(line)
        or "|" in line
    )


def _split_row(line: str) -> list[list[Span]]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [parse_spans(cell.strip()) for cell in stripped.split("|")]


def _read_table(lines: list[str], index: int) -> tuple[Table, int]:
    header = _split_row(lines[index])
    index += 2  # encabezado y fila de guiones
    rows: list[list[list[Span]]] = []
    while index < len(lines) and "|" in lines[index] and lines[index].strip():
        if not _is_divider(lines[index]):
            rows.append(_split_row(lines[index]))
        index += 1
    return Table(header=header, rows=rows), index


def _read_list(lines: list[str], index: int) -> tuple[ListBlock, int]:
    ordered = _ORDERED.match(lines[index]) is not None
    pattern = _ORDERED if ordered else _BULLET
    items: list[list[Span]] = []
    while index < len(lines):
        match = pattern.match(lines[index])
        if not match:
            break
        items.append(parse_spans(match.group(1).strip()))
        index += 1
    return ListBlock(ordered=ordered, items=items), index
