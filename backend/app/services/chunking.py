"""Particionado de notas Markdown de Obsidian en chunks para RAG."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SKIP_DIR_NAMES = {".obsidian", ".trash", ".git"}
MAX_TOKENS = 800
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class MarkdownChunk:
    content: str
    heading: str
    title: str


def estimate_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, len(stripped) // 4)


def iter_markdown_files(vault_root: Path) -> Iterator[Path]:
    """Recorre `*.md` del vault, omitiendo carpetas internas de Obsidian/Git."""
    root = vault_root.resolve()
    for path in sorted(root.rglob("*.md")):
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_DIR_NAMES for part in relative_parts[:-1]):
            continue
        yield path


def extract_title(text: str, filename_stem: str) -> str:
    meta, body = _split_frontmatter(text)
    frontmatter_title = (meta.get("title") or "").strip()
    if frontmatter_title:
        return frontmatter_title
    heading_title = _first_h1(body)
    if heading_title:
        return heading_title
    return filename_stem


def chunk_markdown(text: str, *, filename_stem: str = "nota") -> list[MarkdownChunk]:
    """Divide un archivo Markdown respetando encabezados como límites naturales.

    Objetivo: chunks de ~500-800 tokens (`len(text)//4`). Secciones pequeñas
    se empaquetan juntas; una sección que exceda el máximo se parte por
    párrafos y oraciones. Cada chunk incluye el breadcrumb de headings.
    """
    _meta, body = _split_frontmatter(text)
    title = extract_title(text, filename_stem)
    units: list[tuple[str, str]] = []
    for heading, section_body in _parse_sections(body):
        heading_tokens = estimate_tokens(heading) + (2 if heading else 0)
        body_budget = max(1, MAX_TOKENS - heading_tokens)
        if estimate_tokens(section_body) > body_budget:
            pieces = _split_oversized(section_body, body_budget)
        else:
            pieces = [section_body] if section_body.strip() else []
        for piece in pieces:
            formatted = _with_heading(heading, piece)
            if formatted:
                units.append((heading, formatted))

    if not units:
        return []

    chunks: list[MarkdownChunk] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0
    for heading, formatted in units:
        tokens = estimate_tokens(formatted)
        if current and current_tokens + tokens > MAX_TOKENS:
            chunks.append(_to_chunk(current, title))
            current = [(heading, formatted)]
            current_tokens = tokens
        else:
            current.append((heading, formatted))
            current_tokens += tokens
    if current:
        chunks.append(_to_chunk(current, title))
    return chunks


def _to_chunk(parts: list[tuple[str, str]], title: str) -> MarkdownChunk:
    heading = parts[0][0]
    content = "\n\n".join(formatted for _, formatted in parts)
    return MarkdownChunk(content=content, heading=heading, title=title)


def _with_heading(heading: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    if heading:
        return f"{heading}\n\n{body}"
    return body


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[4:end] if text.startswith("---\n") else text[3:end]
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    return meta, body


def _first_h1(body: str) -> str:
    for line in body.splitlines():
        match = H1_RE.match(line)
        if match:
            return match.group(1).strip()
    return ""


def _parse_sections(body: str) -> list[tuple[str, str]]:
    """Devuelve (breadcrumb, cuerpo) por cada bloque entre encabezados ATX."""
    lines = body.splitlines()
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        buffer.clear()
        if not text:
            return
        breadcrumb = " > ".join(title for _, title in stack)
        sections.append((breadcrumb, text))

    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            continue
        buffer.append(line)
    flush()
    return sections


def _split_oversized(text: str, max_tokens: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return _split_by_sentences(text, max_tokens)

    packed: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for paragraph in paragraphs:
        tokens = estimate_tokens(paragraph)
        if tokens > max_tokens:
            if current:
                packed.append("\n\n".join(current))
                current, current_tokens = [], 0
            packed.extend(_split_by_sentences(paragraph, max_tokens))
            continue
        if current and current_tokens + tokens > max_tokens:
            packed.append("\n\n".join(current))
            current, current_tokens = [paragraph], tokens
        else:
            current.append(paragraph)
            current_tokens += tokens
    if current:
        packed.append("\n\n".join(current))
    return packed


def _split_by_sentences(text: str, max_tokens: int) -> list[str]:
    sentences = [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]
    if len(sentences) <= 1:
        return _split_by_chars(text, max_tokens)

    packed: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for sentence in sentences:
        tokens = estimate_tokens(sentence)
        if tokens > max_tokens:
            if current:
                packed.append(" ".join(current))
                current, current_tokens = [], 0
            packed.extend(_split_by_chars(sentence, max_tokens))
            continue
        if current and current_tokens + tokens > max_tokens:
            packed.append(" ".join(current))
            current, current_tokens = [sentence], tokens
        else:
            current.append(sentence)
            current_tokens += tokens
    if current:
        packed.append(" ".join(current))
    return packed


def _split_by_chars(text: str, max_tokens: int) -> list[str]:
    max_chars = max(max_tokens * 4, 1)
    stripped = text.strip()
    if estimate_tokens(stripped) <= max_tokens:
        return [stripped] if stripped else []

    pieces: list[str] = []
    remaining = stripped
    while remaining:
        if estimate_tokens(remaining) <= max_tokens:
            pieces.append(remaining)
            break
        window = remaining[:max_chars]
        split_at = window.rfind(" ")
        if split_at < max_chars // 4:
            split_at = max_chars
        piece = remaining[:split_at].strip()
        remaining = remaining[split_at:].strip()
        if piece:
            pieces.append(piece)
    return pieces
