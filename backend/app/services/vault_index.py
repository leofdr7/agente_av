"""Indexación incremental del vault de Obsidian en `knowledge_chunks`."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from supabase import Client

from app.core.config import settings
from app.services.chunking import MarkdownChunk, chunk_markdown, iter_markdown_files
from app.services.embeddings import InputType, embed_texts

PAGE_SIZE = 1000
INSERT_BATCH = 50
EmbedFn = Callable[[Sequence[str], InputType], list[list[float]]]
T = TypeVar("T")


@dataclass(frozen=True)
class IndexStats:
    files_seen: int = 0
    files_skipped: int = 0
    files_reindexed: int = 0
    chunks_upserted: int = 0
    chunks_purged: int = 0


def hash_chunk(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def default_vault_path() -> Path:
    if settings.vault_path:
        return Path(settings.vault_path).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "vault"


def index_vault(
    vault_root: Path,
    client: Client,
    *,
    embed_fn: EmbedFn | None = None,
) -> IndexStats:
    """Recorre el vault, reindexa archivos cuyo hash cambió y elimina huérfanos."""
    root = vault_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"El vault no existe o no es un directorio: {root}")

    embed = embed_fn or embed_texts
    existing_by_path = _group_existing(_fetch_existing_chunks(client))
    live_paths: set[str] = set()

    files_seen = 0
    files_skipped = 0
    files_reindexed = 0
    chunks_upserted = 0

    for path in iter_markdown_files(root):
        files_seen += 1
        relative = path.relative_to(root).as_posix()
        live_paths.add(relative)
        text = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, filename_stem=path.stem)
        new_hashes = sorted(hash_chunk(chunk.content) for chunk in chunks)
        existing_rows = existing_by_path.get(relative, [])
        existing_hashes = sorted(row.get("content_hash") or "" for row in existing_rows)
        unchanged = new_hashes == existing_hashes and (
            not new_hashes or all(existing_hashes)
        )
        if unchanged:
            files_skipped += 1
            continue

        if existing_rows:
            _delete_ids(client, [row["id"] for row in existing_rows])

        if chunks:
            modified_at = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            vectors = embed([chunk.content for chunk in chunks], "document")
            rows = [
                _chunk_row(relative, chunk, vector, modified_at)
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            _insert_rows(client, rows)
            chunks_upserted += len(rows)

        files_reindexed += 1

    # Un vault sin .md (p. ej. solo .gitkeep) no debe vaciar la base por error.
    if files_seen == 0:
        return IndexStats()

    chunks_purged = 0
    for path_key, rows in existing_by_path.items():
        if path_key in live_paths:
            continue
        ids = [row["id"] for row in rows]
        _delete_ids(client, ids)
        chunks_purged += len(ids)

    return IndexStats(
        files_seen=files_seen,
        files_skipped=files_skipped,
        files_reindexed=files_reindexed,
        chunks_upserted=chunks_upserted,
        chunks_purged=chunks_purged,
    )


def _chunk_row(
    obsidian_path: str,
    chunk: MarkdownChunk,
    embedding: list[float],
    modified_at: str,
) -> dict:
    return {
        "content": chunk.content,
        "embedding": embedding,
        "content_hash": hash_chunk(chunk.content),
        "metadata": {
            "obsidian_path": obsidian_path,
            "title": chunk.title,
            "modified_at": modified_at,
            "heading": chunk.heading,
        },
    }


def _fetch_existing_chunks(client: Client) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        result = (
            client.table("knowledge_chunks")
            .select("id, content_hash, metadata")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def _group_existing(rows: list[dict]) -> dict[str | None, list[dict]]:
    grouped: dict[str | None, list[dict]] = defaultdict(list)
    for row in rows:
        metadata = row.get("metadata") or {}
        path = metadata.get("obsidian_path")
        grouped[path].append(row)
    return grouped


def _delete_ids(client: Client, ids: list[object]) -> None:
    if not ids:
        return
    for batch in _chunks_of(ids, INSERT_BATCH):
        client.table("knowledge_chunks").delete().in_("id", batch).execute()


def _insert_rows(client: Client, rows: list[dict]) -> None:
    for batch in _chunks_of(rows, INSERT_BATCH):
        client.table("knowledge_chunks").insert(batch).execute()


def _chunks_of(items: list[T], size: int) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
