#!/usr/bin/env python3
"""Carga AWS-3 desde una terminal local sin poner claves en argumentos ni logs."""

import base64
import getpass
import hmac
import json
import re
import subprocess
import sys
import time


PROFILE = "agenta-operator"
REGION = "us-east-2"
ACCOUNT = "964862484349"
PREFIX = "agenta/production/"
ROLE = "ecsTaskExecutionRole"
POLICY_NAME = "agenta-production-secrets"
KEYS = (
    "ANTHROPIC_API_KEY",
    "SUPABASE_SERVICE_KEY",
    "CLERK_SECRET_KEY",
    "OPENAI_API_KEY",
)


class AwsError(RuntimeError):
    def __init__(self, service: str, operation: str, stderr: bytes, returncode: int):
        # Solo se extrae el identificador del error. Nunca se imprime la respuesta completa.
        match = re.search(rb"\(([A-Za-z0-9]+)\) when calling", stderr)
        self.code = match.group(1).decode("ascii") if match else "Unknown"
        super().__init__(f"AWS {service} {operation} falló ({self.code}; código {returncode}).")


def aws(service: str, operation: str, *args: str, stdin: bytes | None = None) -> dict:
    command = [
        "aws", service, operation, *args,
        "--profile", PROFILE, "--region", REGION,
        "--output", "json", "--no-cli-pager",
    ]
    for attempt in range(4):
        result = subprocess.run(command, input=stdin, capture_output=True, check=False)
        if not result.returncode:
            return json.loads(result.stdout or b"{}")
        error = AwsError(service, operation, result.stderr, result.returncode)
        if error.code not in {"AccessDenied", "AccessDeniedException"} or attempt == 3:
            raise error
        # IAM puede tardar en propagar una política recién adjunta.
        time.sleep(2 ** attempt)
    raise AssertionError("Bucle de AWS sin resultado")


def validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{name}: valor vacío o con espacios/saltos de línea.")
    if name == "SUPABASE_SERVICE_KEY":
        parts = value.split(".")
        if len(parts) != 3 or len(value) < 100:
            raise ValueError("SUPABASE_SERVICE_KEY debe ser el JWT real, no el placeholder.")
        try:
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("SUPABASE_SERVICE_KEY no tiene una carga JWT válida.") from exc
        if payload.get("role") != "service_role":
            raise ValueError("SUPABASE_SERVICE_KEY debe tener rol service_role.")


def list_named_secrets() -> dict[str, str]:
    result = aws(
        "secretsmanager", "list-secrets",
        "--filters", f"Key=name,Values={PREFIX}",
    )
    return {
        item["Name"]: item["ARN"]
        for item in result.get("SecretList", [])
        if item["Name"] in {PREFIX + key for key in KEYS}
    }


def wait_for_listed_secrets(arns: dict[str, str]) -> None:
    # ListSecrets puede tardar hasta cinco minutos en reflejar un alta.
    deadline = time.monotonic() + 360
    delay = 2
    while True:
        listed = list_named_secrets()
        if all(listed.get(PREFIX + key) == arns[PREFIX + key] for key in KEYS):
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("La comprobación de list-secrets no encontró los cuatro ARN esperados.")
        print("Esperando consistencia de list-secrets...", flush=True)
        time.sleep(min(delay, remaining))
        delay = min(delay * 2, 60)


def wait_for_role_policy(policy: dict) -> None:
    deadline = time.monotonic() + 60
    while True:
        try:
            attached = aws("iam", "get-role-policy", "--role-name", ROLE, "--policy-name", POLICY_NAME)
        except AwsError as exc:
            if exc.code not in {"NoSuchEntity", "NoSuchEntityException"}:
                raise
        else:
            document = attached.get("PolicyDocument")
            if isinstance(document, str):
                document = json.loads(document)
            if document == policy:
                return
        if time.monotonic() >= deadline:
            raise RuntimeError("La política inline recuperada difiere de los cuatro ARN exactos.")
        time.sleep(3)


def verify_operator() -> None:
    identity = aws("sts", "get-caller-identity")
    expected_identity = f"arn:aws:iam::{ACCOUNT}:user/leofdr7"
    if identity.get("Arn") != expected_identity:
        raise RuntimeError("La identidad AWS activa no es el usuario IAM de AWS-1.")


def wait_for_current_version(arn: str, version_id: str) -> None:
    deadline = time.monotonic() + 60
    while True:
        metadata = aws("secretsmanager", "describe-secret", "--secret-id", arn)
        stages = metadata.get("VersionIdsToStages", {}).get(version_id, [])
        if "AWSCURRENT" in stages:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("La versión nueva aún no tiene la etiqueta AWSCURRENT.")
        time.sleep(3)


def rotate_main() -> int:
    if not sys.stdin.isatty():
        raise RuntimeError("Ejecuta este programa en una terminal interactiva.")
    verify_operator()

    # Se comprueba la existencia de las cuatro claves antes de pedir ningún valor.
    arns = {}
    for key in KEYS:
        metadata = aws("secretsmanager", "describe-secret", "--secret-id", PREFIX + key)
        arns[key] = metadata["ARN"]

    for key in KEYS:
        value = getpass.getpass(f"{key} (nuevo): ")
        confirmation = getpass.getpass(f"{key} (repetir): ")
        if not hmac.compare_digest(value, confirmation):
            raise ValueError(f"{key}: las dos entradas no coinciden.")
        validate_key(key, value)
        result = aws(
            "secretsmanager", "put-secret-value",
            "--secret-id", arns[key],
            "--secret-string", "file:///dev/stdin",
            stdin=value.encode("utf-8"),
        )
        del value, confirmation
        wait_for_current_version(arns[key], result["VersionId"])
        print(f"Actualizado y verificado: {PREFIX + key}", flush=True)

    print("Rotación validada: las cuatro versiones nuevas tienen AWSCURRENT.")
    return 0


def main() -> int:
    if not sys.stdin.isatty():
        raise RuntimeError("Ejecuta este programa en una terminal interactiva.")

    verify_operator()

    # Las consultas de permisos ocurren antes de pedir cualquier clave.
    list_named_secrets()
    try:
        aws("iam", "get-role-policy", "--role-name", ROLE, "--policy-name", POLICY_NAME)
    except AwsError as exc:
        if exc.code not in {"NoSuchEntity", "NoSuchEntityException"}:
            raise

    arns = {}
    for key in KEYS:
        name = PREFIX + key
        try:
            metadata = aws("secretsmanager", "describe-secret", "--secret-id", name)
        except AwsError as exc:
            if exc.code != "ResourceNotFoundException":
                raise
        else:
            arns[name] = metadata["ARN"]
            print(f"Ya existe: {name}. Se conserva su versión actual.", flush=True)
            continue
        value = getpass.getpass(f"{key}: ")
        validate_key(key, value)
        result = aws(
            "secretsmanager", "create-secret",
            "--name", name,
            "--secret-string", "file:///dev/stdin",
            stdin=value.encode("utf-8"),
        )
        arns[name] = result["ARN"]
        del value
        print(f"Creado: {name}", flush=True)

    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "GetOnlyAws3ProductionSecrets",
            "Effect": "Allow",
            "Action": "secretsmanager:GetSecretValue",
            "Resource": [arns[PREFIX + key] for key in KEYS],
        }],
    }
    aws(
        "iam", "put-role-policy",
        "--role-name", ROLE,
        "--policy-name", POLICY_NAME,
        "--policy-document", "file:///dev/stdin",
        stdin=json.dumps(policy).encode("utf-8"),
    )

    wait_for_listed_secrets(arns)
    wait_for_role_policy(policy)

    print("AWS-3 validada: cuatro secretos presentes y política limitada a sus ARN exactos.")
    for key in KEYS:
        print(f"{PREFIX + key}: {arns[PREFIX + key]}")
    return 0


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--rotate"]:
            raise SystemExit(rotate_main())
        if sys.argv[1:]:
            raise ValueError("Uso: python3 infra/aws/create-production-secrets.py [--rotate]")
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
