"""Indexa el vault de Obsidian en `knowledge_chunks`.

    python scripts/index_vault.py
    python scripts/index_vault.py --vault /ruta/al/vault
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.supabase import get_supabase_client
from app.services.vault_index import default_vault_path, index_vault


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/index_vault.py",
        description=(
            "Recorre un vault de Obsidian, genera embeddings y los guarda "
            "en knowledge_chunks (omite chunks cuyo hash no cambió)."
        ),
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help="Carpeta del vault. Por defecto VAULT_PATH o <repo>/vault.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    vault_root = args.vault.resolve() if args.vault else default_vault_path()
    stats = index_vault(vault_root, get_supabase_client())
    print(
        "Indexación lista: "
        f"{stats.files_seen} archivos, "
        f"{stats.files_skipped} sin cambios, "
        f"{stats.files_reindexed} reindexados, "
        f"{stats.chunks_upserted} chunks escritos, "
        f"{stats.chunks_purged} huérfanos eliminados."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:  # noqa: BLE001
        print(f"Error al indexar el vault: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc
