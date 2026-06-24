from __future__ import annotations
import sqlite3
from app.models.schemas import BibleEntry
from app.ai.rag.embeddings import Embedder
from app.ai.rag.vector_store import VectorStore


class StoryBible:
    def __init__(self, conn: sqlite3.Connection, embedder: Embedder, store: VectorStore) -> None:
        self._conn = conn
        self._embedder = embedder
        self._store = store

    def add_entry(self, world_id: str, kind: str, ref_id: str, text: str) -> BibleEntry:
        entry = BibleEntry(id=f"bible_{kind}_{ref_id}", world_id=world_id,
                           kind=kind, ref_id=ref_id, text=text)
        self._conn.execute(
            "INSERT OR REPLACE INTO bible_entries (id, world_id, kind, ref_id, text) VALUES (?, ?, ?, ?, ?)",
            (entry.id, entry.world_id, entry.kind, entry.ref_id, entry.text),
        )
        self._conn.commit()
        self._store.add(entry.id, self._embedder.embed([text])[0])
        return entry

    def _row_to_entry(self, row) -> BibleEntry:
        return BibleEntry(id=row["id"], world_id=row["world_id"], kind=row["kind"],
                          ref_id=row["ref_id"], text=row["text"])

    def search(self, query: str, k: int = 5) -> list[BibleEntry]:
        vec = self._embedder.embed([query])[0]
        hits = self._store.query(vec, k=k)
        out: list[BibleEntry] = []
        for entry_id, _score in hits:
            row = self._conn.execute("SELECT * FROM bible_entries WHERE id = ?", (entry_id,)).fetchone()
            if row is not None:
                out.append(self._row_to_entry(row))
        return out

    def all_entries(self, world_id: str) -> list[BibleEntry]:
        rows = self._conn.execute("SELECT * FROM bible_entries WHERE world_id = ?", (world_id,)).fetchall()
        return [self._row_to_entry(r) for r in rows]
