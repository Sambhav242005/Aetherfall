from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from app.ai.rag.story_bible import StoryBible
from app.ai.worldbuilder import load_world_bible, render_world_bible


@dataclass
class RetrievedContext:
    world_facts: str
    bible_slice: str

    def pack(self, char_budget: int) -> str:
        combined = self.world_facts
        remaining = char_budget - len(combined)
        if remaining > 0 and self.bible_slice:
            combined = combined + ("\n" if combined else "") + self.bible_slice
        return combined[:char_budget]


class Retriever:
    def __init__(self, conn: sqlite3.Connection, bible: StoryBible, world_id=None) -> None:
        self._conn = conn
        self._bible = bible
        self._world_id = world_id

    def _rows(self, table: str, ids: list[str] | None) -> list:
        if ids is None:
            return self._conn.execute(f"SELECT * FROM {table}").fetchall()
        if not ids:
            return []
        marks = ",".join("?" for _ in ids)
        return self._conn.execute(f"SELECT * FROM {table} WHERE id IN ({marks})", ids).fetchall()

    def world_facts(self, location_ids=None, character_ids=None, faction_ids=None) -> str:
        lines: list[str] = []
        if self._world_id is not None:
            wb = load_world_bible(self._conn, self._world_id)
            if wb is not None:
                canon = render_world_bible(wb)
                if canon:
                    lines.append(canon)
        for s in self._rows("structures", location_ids):
            lines.append(f"LOCATION {s['id']}: {s['type']} (layer {s['layer']})")
        for n in self._rows("npcs", character_ids):
            lines.append(f"CHARACTER {n['id']}: {n['name']}, {n['role']}, at {n['location_id']}")
        for f in self._rows("factions", faction_ids):
            lines.append(f"FACTION {f['id']}: {f['name']}")
        return "\n".join(lines)

    def retrieve(self, query, *, k=5, location_ids=None, character_ids=None, faction_ids=None) -> RetrievedContext:
        facts = self.world_facts(location_ids, character_ids, faction_ids)
        entries = self._bible.search(query, k=k)
        bible_slice = "\n".join(f"[{e.kind}:{e.ref_id}] {e.text}" for e in entries)
        return RetrievedContext(world_facts=facts, bible_slice=bible_slice)
