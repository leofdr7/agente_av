from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.chunking import chunk_markdown
from app.services.vault_index import hash_chunk, index_vault


class FakeTable:
    def __init__(self, existing: list[dict]) -> None:
        self.existing = existing
        self.deleted_ids: list[object] = []
        self.inserted: list[dict] = []

    def select(self, *_args, **_kwargs):
        return self

    def range(self, *_args, **_kwargs):
        return self

    def delete(self):
        return self

    def in_(self, _column, ids):
        self.deleted_ids.extend(ids)
        return self

    def insert(self, rows):
        self.inserted.extend(rows)
        return self

    def execute(self):
        return MagicMock(data=list(self.existing))


def _client(existing: list[dict] | None = None) -> tuple[MagicMock, FakeTable]:
    table = FakeTable(existing or [])
    client = MagicMock()
    client.table.return_value = table
    return client, table


def _embed(texts, input_type="document"):
    return [[float(len(texts))] * 512 for _ in texts]


def _write_note(root: Path, relative: str, body: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_skips_unchanged_chunks(tmp_path: Path) -> None:
    path = _write_note(tmp_path, "nota.md", "# Hola\n\ncontenido estable\n")
    chunks = chunk_markdown(path.read_text(encoding="utf-8"), filename_stem=path.stem)
    existing = [
        {
            "id": str(uuid4()),
            "content_hash": hash_chunk(chunk.content),
            "metadata": {"obsidian_path": "nota.md"},
        }
        for chunk in chunks
    ]
    client, table = _client(existing)
    embed_fn = MagicMock(side_effect=_embed)

    stats = index_vault(tmp_path, client, embed_fn=embed_fn)

    assert stats.files_skipped == 1
    assert stats.files_reindexed == 0
    embed_fn.assert_not_called()
    assert table.inserted == []
    assert table.deleted_ids == []


def test_replaces_changed_file(tmp_path: Path) -> None:
    _write_note(tmp_path, "nota.md", "# Hola\n\ncontenido nuevo\n")
    old_id = str(uuid4())
    client, table = _client(
        [
            {
                "id": old_id,
                "content_hash": "hash-viejo",
                "metadata": {"obsidian_path": "nota.md"},
            }
        ]
    )

    stats = index_vault(tmp_path, client, embed_fn=_embed)

    assert stats.files_reindexed == 1
    assert old_id in table.deleted_ids
    assert len(table.inserted) == stats.chunks_upserted
    assert table.inserted[0]["metadata"]["obsidian_path"] == "nota.md"
    assert table.inserted[0]["metadata"]["title"] == "Hola"
    assert "modified_at" in table.inserted[0]["metadata"]
    assert len(table.inserted[0]["embedding"]) == 512


def test_purges_orphan_paths(tmp_path: Path) -> None:
    _write_note(tmp_path, "sigue.md", "# Sigue\n\ntexto\n")
    gone_id = str(uuid4())
    live_chunks = chunk_markdown("# Sigue\n\ntexto\n", filename_stem="sigue")
    client, table = _client(
        [
            {
                "id": gone_id,
                "content_hash": "x",
                "metadata": {"obsidian_path": "borrada.md"},
            },
            {
                "id": str(uuid4()),
                "content_hash": hash_chunk(live_chunks[0].content),
                "metadata": {"obsidian_path": "sigue.md"},
            },
        ]
    )

    stats = index_vault(tmp_path, client, embed_fn=_embed)

    assert gone_id in table.deleted_ids
    assert stats.chunks_purged == 1
    assert stats.files_skipped == 1


def test_empty_vault_does_not_purge(tmp_path: Path) -> None:
    client, table = _client(
        [
            {
                "id": str(uuid4()),
                "content_hash": "x",
                "metadata": {"obsidian_path": "a.md"},
            }
        ]
    )

    stats = index_vault(tmp_path, client, embed_fn=_embed)

    assert stats.files_seen == 0
    assert stats.chunks_purged == 0
    assert table.deleted_ids == []
    assert table.inserted == []
