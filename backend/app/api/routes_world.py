from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.models.schemas import Chunk, Layer
from app.engine.world_generator import generate_world
from app.engine.chunk_manager import generate_chunk
from app.persistence.database import get_connection, init_db
import json

router = APIRouter(prefix="/api/world")


@router.post("/new")
def create_world(seed: int | None = None):
    init_db()
    world_data = generate_world(seed)
    conn = get_connection()
    try:
        world = world_data["world"]
        conn.execute(
            "INSERT OR REPLACE INTO worlds (id, seed, name, base_generated_version, current_tick, regions) VALUES (?, ?, ?, ?, ?, ?)",
            (world["id"], world["seed"], world["name"], world["base_generated_version"], world["current_tick"], json.dumps(world["regions"])),
        )
        for s in world_data["structures"]:
            conn.execute(
                "INSERT OR REPLACE INTO structures (id, world_id, type, layer, position, footprint, influence_zone, exclusion_zone, entrances, owner_faction_id, power_influence, story_hooks) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s["id"], s["world_id"], s["type"], s["layer"], json.dumps(s["position"]), json.dumps(s["footprint"]), json.dumps(s["influence_zone"]), json.dumps(s["exclusion_zone"]), json.dumps(s["entrances"]), s["owner_faction_id"], json.dumps(s["power_influence"]), json.dumps(s["story_hooks"])),
            )
        for e in world_data["entrance_contracts"]:
            conn.execute(
                "INSERT OR REPLACE INTO entrance_contracts (id, source_layer, source_position, target_layer, target_position, access_type, is_returnable, locked_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (e["id"], e["source_layer"], json.dumps(e["source_position"]), e["target_layer"], json.dumps(e["target_position"]), e["access_type"], 1 if e["is_returnable"] else 0, e["locked_by"]),
            )
        for f in world_data["factions"]:
            conn.execute(
                "INSERT OR REPLACE INTO factions (id, name, principle_bias, home_structure_id, goals, relationships) VALUES (?, ?, ?, ?, ?, ?)",
                (f["id"], f["name"], json.dumps(f["principle_bias"]), f["home_structure_id"], json.dumps(f["goals"]), json.dumps(f["relationships"])),
            )
        for n in world_data["npcs"]:
            conn.execute(
                "INSERT OR REPLACE INTO npcs (id, name, faction_id, location_id, role, personality_tags, known_facts, secrets, power_profile, alive) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (n["id"], n["name"], n["faction_id"], n["location_id"], n["role"], json.dumps(n["personality_tags"]), json.dumps(n["known_facts"]), json.dumps(n["secrets"]), json.dumps(n["power_profile"]), 1 if n["alive"] else 0),
            )
        conn.commit()
    finally:
        conn.close()

    return world_data


@router.get("/{world_id}/chunk/{layer}/{chunk_x}/{chunk_y}")
def get_chunk(world_id: str, layer: Layer, chunk_x: int, chunk_y: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT seed FROM worlds WHERE id = ?",
            (world_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="World not found")

    chunk = generate_chunk(world_id, row["seed"], layer, chunk_x, chunk_y)
    return chunk.model_dump(mode="json")


@router.get("/{world_id}/snapshot")
def get_snapshot(world_id: str):
    conn = get_connection()
    try:
        world_row = conn.execute("SELECT * FROM worlds WHERE id = ?", (world_id,)).fetchone()
        if world_row is None:
            raise HTTPException(status_code=404, detail="World not found")

        structures = [dict(r) for r in conn.execute("SELECT * FROM structures WHERE world_id = ?", (world_id,)).fetchall()]
        factions = [dict(r) for r in conn.execute("SELECT * FROM factions").fetchall()]
        npcs = [dict(r) for r in conn.execute("SELECT * FROM npcs").fetchall()]
        entrances = [dict(r) for r in conn.execute("SELECT * FROM entrance_contracts").fetchall()]

        return {
            "world": dict(world_row),
            "structures": structures,
            "factions": factions,
            "npcs": npcs,
            "entrance_contracts": entrances,
        }
    finally:
        conn.close()
