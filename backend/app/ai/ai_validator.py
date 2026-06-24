from __future__ import annotations
import sqlite3
from app.models.schemas import AIProposal

FORBIDDEN_KEYS = {"inventory", "damage", "death", "ownership", "quest_completion", "map_geometry"}


def _exists(conn: sqlite3.Connection, table: str, id_: str) -> bool:
    return conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (id_,)).fetchone() is not None


def validate_proposal(proposal: AIProposal, conn: sqlite3.Connection) -> list[str]:
    reasons: list[str] = []
    payload = proposal.payload or {}

    for key in FORBIDDEN_KEYS:
        if key in payload:
            reasons.append(f"proposal attempts forbidden state mutation: '{key}'")

    loc = payload.get("location_id")
    if loc is not None and not _exists(conn, "structures", loc):
        reasons.append(f"location does not exist: {loc}")

    for cid in payload.get("character_ids", []) or []:
        if not _exists(conn, "npcs", cid):
            reasons.append(f"character does not exist: {cid}")

    for fid in payload.get("faction_ids", []) or []:
        if not _exists(conn, "factions", fid):
            reasons.append(f"faction does not exist: {fid}")

    return reasons
