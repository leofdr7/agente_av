"""Entrypoint de consola para resolver AX=B sin pasar por la API.

    python -m app.cli.linear_systems sistema.json
    python -m app.cli.linear_systems --stdin < sistema.json

El JSON de entrada tiene la forma {"A": [[...], ...], "B": [...]} y admite una
clave opcional "variable_names" para etiquetar las componentes en el diagnóstico
de infactibilidad.

Códigos de salida: 0 resuelto, 1 sistema singular, 2 entrada inválida, 3 fallo
interno del motor.
"""

import argparse
import json
import sys
from typing import Any

from pydantic import ValidationError

from app.models.linear_system import LinearSystemInput
from app.services.linear_systems_engine import (
    MethodInconsistencyError,
    solve_linear_system,
)

EXIT_OK = 0
EXIT_SINGULAR = 1
EXIT_INVALID_INPUT = 2
EXIT_ENGINE_ERROR = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.linear_systems",
        description="Resuelve AX=B por Gauss, Gauss-Jordan y matriz inversa.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Archivo JSON con A y B. Si se omite o es '-', se lee de stdin.",
    )
    parser.add_argument(
        "--stdin", action="store_true", help="Fuerza la lectura desde stdin."
    )
    parser.add_argument(
        "--no-steps",
        action="store_true",
        help="Omite la traza de operaciones de fila en la salida.",
    )
    parser.add_argument("--indent", type=int, default=2, help="Sangría del JSON.")
    return parser


def _read_payload(args: argparse.Namespace) -> Any:
    if args.stdin or args.path in (None, "-"):
        return json.load(sys.stdin)
    with open(args.path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        payload = _read_payload(args)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"No se pudo leer el sistema de entrada: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if not isinstance(payload, dict):
        print("El JSON de entrada debe ser un objeto con las claves A y B.", file=sys.stderr)
        return EXIT_INVALID_INPUT

    try:
        system = LinearSystemInput(A=payload.get("A"), B=payload.get("B"))
    except ValidationError as exc:
        print(f"Entrada inválida:\n{exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    try:
        result = solve_linear_system(system, payload.get("variable_names"))
    except MethodInconsistencyError as exc:
        print(f"Error interno del motor: {exc}", file=sys.stderr)
        return EXIT_ENGINE_ERROR

    output = result.model_dump(mode="json")
    if args.no_steps:
        for method in output["methods"]:
            method.pop("steps", None)
            method.pop("component_steps", None)

    print(json.dumps(output, indent=args.indent, ensure_ascii=False))

    if not result.solved:
        print(f"\n{result.diagnosis.message}", file=sys.stderr)
        return EXIT_SINGULAR
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
