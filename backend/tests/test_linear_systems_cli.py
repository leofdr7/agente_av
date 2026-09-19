import io
import json

import pytest

from app.cli.linear_systems import (
    EXIT_INVALID_INPUT,
    EXIT_OK,
    EXIT_SINGULAR,
    main,
)
from tests.fixtures import techchip


def write_system(tmp_path, A, B, **extra) -> str:
    path = tmp_path / "sistema.json"
    path.write_text(json.dumps({"A": A, "B": B, **extra}), encoding="utf-8")
    return str(path)


def test_cli_solves_from_file(tmp_path, capsys) -> None:
    path = write_system(
        tmp_path, techchip.A, techchip.DATASET_B, variable_names=techchip.VARIABLE_NAMES
    )

    exit_code = main([path, "--no-steps"])

    assert exit_code == EXIT_OK
    body = json.loads(capsys.readouterr().out)
    assert body["solution"] == pytest.approx(techchip.X_ESPERADA, abs=1e-6)
    assert "steps" not in body["methods"][0]


def test_cli_reads_from_stdin(tmp_path, capsys, monkeypatch) -> None:
    payload = json.dumps({"A": techchip.A, "B": techchip.DATASET_B})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))

    exit_code = main(["--stdin"])

    assert exit_code == EXIT_OK
    assert json.loads(capsys.readouterr().out)["solved"] is True


def test_cli_exits_with_code_1_on_singular_system(tmp_path, capsys) -> None:
    degenerate = [list(row) for row in techchip.A]
    degenerate[5] = [2 * value for value in techchip.A[0]]
    path = write_system(tmp_path, degenerate, techchip.DATASET_B)

    exit_code = main([path])

    assert exit_code == EXIT_SINGULAR
    captured = capsys.readouterr()
    assert json.loads(captured.out)["solution"] is None
    assert "incompatible" in captured.err.lower()


def test_cli_exits_with_code_2_on_invalid_input(tmp_path, capsys) -> None:
    path = write_system(tmp_path, [[1, 2], [3, 4]], [1, 2, 3])

    exit_code = main([path])

    assert exit_code == EXIT_INVALID_INPUT
    assert "Entrada inválida" in capsys.readouterr().err
