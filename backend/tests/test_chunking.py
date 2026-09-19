from pathlib import Path

from app.services.chunking import (
    MAX_TOKENS,
    chunk_markdown,
    estimate_tokens,
    extract_title,
    iter_markdown_files,
)


def _fill(token_count: int, char: str = "a") -> str:
    return char * (token_count * 4)


def test_extract_title_from_frontmatter() -> None:
    text = "---\ntitle: Extrusión\n---\n\n# Otro\n\ncuerpo"
    assert extract_title(text, "archivo") == "Extrusión"


def test_extract_title_from_h1_or_filename() -> None:
    assert extract_title("# Temperatura\n\ncuerpo", "nota") == "Temperatura"
    assert extract_title("solo cuerpo", "mi-nota") == "mi-nota"


def test_headers_are_natural_chunk_boundaries() -> None:
    text = (
        "# Título\n\n"
        f"## Uno\n\n{_fill(600, 'a')}\n\n"
        f"## Dos\n\n{_fill(600, 'b')}\n"
    )
    chunks = chunk_markdown(text, filename_stem="doc")

    assert len(chunks) >= 2
    assert chunks[0].title == "Título"
    assert "Uno" in chunks[0].heading
    assert any("Dos" in chunk.heading for chunk in chunks)
    assert not any("b" * 20 in chunks[0].content for chunk in chunks[:1])
    assert all(estimate_tokens(chunk.content) <= MAX_TOKENS for chunk in chunks)


def test_small_heading_sections_are_packed() -> None:
    text = "## A\n\nuno\n\n## B\n\ndos\n"
    chunks = chunk_markdown(text, filename_stem="doc")
    assert len(chunks) == 1
    assert "uno" in chunks[0].content
    assert "dos" in chunks[0].content


def test_oversized_section_is_split() -> None:
    text = f"# Título\n\n## Largo\n\n{_fill(2000, 'c')}"
    chunks = chunk_markdown(text, filename_stem="doc")
    assert len(chunks) > 1
    assert all(estimate_tokens(chunk.content) <= MAX_TOKENS for chunk in chunks)
    assert all("Largo" in chunk.heading for chunk in chunks)


def test_iter_markdown_skips_obsidian_dirs(tmp_path: Path) -> None:
    (tmp_path / "nota.md").write_text("# Hola\n", encoding="utf-8")
    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "workspace.md").write_text("interno", encoding="utf-8")
    trash = tmp_path / ".trash" / "old"
    trash.mkdir(parents=True)
    (trash / "borrada.md").write_text("no", encoding="utf-8")
    nested = tmp_path / "procesos"
    nested.mkdir()
    (nested / "linea.md").write_text("# Línea\n", encoding="utf-8")

    found = [path.relative_to(tmp_path).as_posix() for path in iter_markdown_files(tmp_path)]
    assert found == ["nota.md", "procesos/linea.md"]
