import json
from app.persistence.database import get_connection, init_db
from app.engine.world_generator import generate_world
from app.models.schemas import AIProposal
from app.ai.ai_validator import validate_proposal


def _world(db):
    init_db(db)
    conn = get_connection(db)
    data = generate_world(seed=7)

    # Insert world
    w = data["world"]
    conn.execute("INSERT INTO worlds (id, seed, name, base_generated_version, current_tick, regions) VALUES (?,?,?,?,?,?)",
                 (w["id"], w["seed"], w["name"], w["base_generated_version"], w["current_tick"], json.dumps(w["regions"])))

    # Insert factions
    for f in data["factions"]:
        conn.execute("INSERT INTO factions (id, name, principle_bias, home_structure_id, goals, relationships) VALUES (?,?,?,?,?,?)",
                     (f["id"], f["name"], json.dumps(f["principle_bias"]), f["home_structure_id"], json.dumps(f["goals"]), json.dumps(f["relationships"])))

    # Insert structures
    for s in data["structures"]:
        conn.execute("INSERT INTO structures (id, world_id, type, layer, position, footprint, influence_zone, exclusion_zone, entrances, owner_faction_id, power_influence, story_hooks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (s["id"], s["world_id"], s["type"], s["layer"], json.dumps(s["position"]), json.dumps(s["footprint"]), json.dumps(s["influence_zone"]), json.dumps(s["exclusion_zone"]), json.dumps(s["entrances"]), s["owner_faction_id"], json.dumps(s["power_influence"]), json.dumps(s["story_hooks"])))

    # Insert NPCs
    for n in data["npcs"]:
        conn.execute("INSERT INTO npcs (id, name, faction_id, location_id, role, personality_tags, known_facts, secrets, power_profile, alive) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (n["id"], n["name"], n["faction_id"], n["location_id"], n["role"], json.dumps(n["personality_tags"]), json.dumps(n["known_facts"]), json.dumps(n["secrets"]), json.dumps(n["power_profile"]), n["alive"]))

    conn.commit()
    return conn


def test_accepts_grounded_proposal(tmp_path):
    conn = _world(tmp_path / "v.db")
    try:
        p = AIProposal(id="p1", proposal_type="scene",
                       payload={"location_id": "struct_moonlake", "character_ids": ["npc_004"]})
        assert validate_proposal(p, conn) == []
    finally:
        conn.close()


def test_rejects_missing_location(tmp_path):
    conn = _world(tmp_path / "v2.db")
    try:
        p = AIProposal(id="p2", proposal_type="scene", payload={"location_id": "struct_atlantis"})
        reasons = validate_proposal(p, conn)
        assert any("struct_atlantis" in r for r in reasons)
    finally:
        conn.close()


def test_rejects_state_mutation(tmp_path):
    conn = _world(tmp_path / "v3.db")
    try:
        p = AIProposal(id="p3", proposal_type="scene",
                       payload={"location_id": "struct_moonlake", "death": "npc_004"})
        reasons = validate_proposal(p, conn)
        assert any("death" in r for r in reasons)
    finally:
        conn.close()
