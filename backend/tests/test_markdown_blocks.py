"""El lector de Markdown se corta solo y no instala manejadores de señal."""

import signal
import threading

import pytest

from app.services.markdown_blocks import (
    Heading,
    MarkdownParseError,
    Span,
    parse_markdown,
)

NORMAL = "## Diagnóstico\n\nEl sistema es **determinado**.\n"


def test_un_timeout_no_deja_manejador_y_la_siguiente_llamada_parsea() -> None:
    before = signal.getsignal(signal.SIGALRM)
    import app.services.markdown_blocks as blocks

    original = blocks.PARSE_TIMEOUT_SECONDS
    blocks.PARSE_TIMEOUT_SECONDS = -1
    try:
        with pytest.raises(MarkdownParseError, match="superó"):
            parse_markdown(NORMAL)
        assert signal.getsignal(signal.SIGALRM) == before

        blocks.PARSE_TIMEOUT_SECONDS = original
        parsed = parse_markdown(NORMAL)
    finally:
        blocks.PARSE_TIMEOUT_SECONDS = original

    assert signal.getsignal(signal.SIGALRM) == before
    headings = [block for block in parsed if isinstance(block, Heading)]
    assert headings and headings[0].spans == [Span("Diagnóstico")]


def test_el_tope_corta_tambien_en_un_hilo_secundario() -> None:
    """El request HTTP no es el hilo principal; el tope tiene que vivir aquí."""
    import app.services.markdown_blocks as blocks

    box: dict[str, object] = {}

    def run() -> None:
        before = signal.getsignal(signal.SIGALRM)
        box["is_main"] = threading.current_thread() is threading.main_thread()
        previous = blocks.PARSE_TIMEOUT_SECONDS
        blocks.PARSE_TIMEOUT_SECONDS = -1
        try:
            parse_markdown("| Pan | Lotes |\n| --- | --- |\n| caja | 4 |\n")
            box["raised"] = False
        except MarkdownParseError:
            box["raised"] = True
        finally:
            blocks.PARSE_TIMEOUT_SECONDS = previous
        box["handler_unchanged"] = signal.getsignal(signal.SIGALRM) == before

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()

    assert box["is_main"] is False
    assert box["raised"] is True
    assert box["handler_unchanged"] is True
