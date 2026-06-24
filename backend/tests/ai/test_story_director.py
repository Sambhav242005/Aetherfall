import json
import pytest
from app.config import Settings
from app.persistence.database import get_connection, init_db
from app.engine.world_generator import generate_world
from app.ai.model_router import ModelRouter
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible
from app.ai.rag.retriever import Retriever
from app.ai.story_director import generate_outline, generate_story
from tests.ai.fakes import FakeAIClient


def _world(db):
    init_db(db)
    conn = get_connection(db)
    data = generate_world(seed=11)
    wid = data["world"]["id"]
    w = data["world"]
    conn.execute("INSERT INTO worlds (id, seed, name, base_generated_version, current_tick, regions) "
                 "VALUES (?,?,?,?,?,?)",
                 (w["id"], w["seed"], w["name"], w["base_generated_version"], w["current_tick"],
                  json.dumps(w["regions"])))
    for s in data["structures"]:
        conn.execute("INSERT INTO structures (id, world_id, type, layer) VALUES (?,?,?,?)",
                     (s["id"], s["world_id"], s["type"], s["layer"]))
    for n in data["npcs"]:
        conn.execute("INSERT INTO npcs (id, name, faction_id, location_id, role) VALUES (?,?,?,?,?)",
                     (n["id"], n["name"], n["faction_id"], n["location_id"], n["role"]))
    conn.commit()
    return conn, wid


_OUTLINE = json.dumps({
    "title": "The Mutated Lake", "premise": "Magic leaks into Moonlake", "theme": "decay",
    "beats": [
        {"act": 1, "summary": "Farmer finds dead fish",
         "location_ids": ["struct_moonlake"], "character_ids": ["npc_001"], "faction_ids": []},
    ],
})
_GOOD_VERDICT = json.dumps({"verdict": "accept",
                            "scores": {"coherence": 8, "voice": 7, "grounding": 8}})


def test_generate_outline_persists(tmp_path):
    conn, wid = _world(tmp_path / "o.db")
    try:
        router = ModelRouter(FakeAIClient([_OUTLINE]),
                             Settings(openrouter_api_key="k", director_models=["d1"], rpm_limit=1000))
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        arc = generate_outline(wid, conn, router, Retriever(conn, bible))
        assert arc.title == "The Mutated Lake"
        beats = conn.execute("SELECT * FROM story_beats WHERE arc_id = ?", (arc.id,)).fetchall()
        assert len(beats) == 1
    finally:
        conn.close()


def test_generate_story_happy_path(tmp_path):
    conn, wid = _world(tmp_path / "s.db")
    try:
        # outline (director) -> draft (worker) -> verdict (verifier) -> summary (worker)
        client = FakeAIClient([_OUTLINE, "A grim scene at Moonlake.", _GOOD_VERDICT, "Farmer sees dead fish."])
        router = ModelRouter(client, Settings(openrouter_api_key="k",
                                              director_models=["d1"], worker_models=["w1"],
                                              verifier_models=["v1"], rpm_limit=1000))
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        retriever = Retriever(conn, bible)
        arc = generate_story(wid, conn, router, retriever, bible, max_repair=2, threshold=6)
        scenes = conn.execute("SELECT * FROM scenes").fetchall()
        assert len(scenes) == 1 and scenes[0]["status"] == "approved"
        assert len(bible.all_entries(wid)) >= 1  # scene summarized into bible
    finally:
        conn.close()


def test_repair_loop_flags_for_review(tmp_path):
    conn, wid = _world(tmp_path / "r.db")
    try:
        bad = json.dumps({"verdict": "revise", "scores": {"coherence": 3}, "fix_hints": ["tighten"]})
        # outline, draft, verdict(bad), revise, verdict(bad), revise, verdict(bad) -> exhaust
        client = FakeAIClient([_OUTLINE, "draft", bad, "rev1", bad, "rev2", bad])
        router = ModelRouter(client, Settings(openrouter_api_key="k",
                                              director_models=["d1"], worker_models=["w1"],
                                              verifier_models=["v1"], rpm_limit=1000))
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        arc = generate_story(wid, conn, router, Retriever(conn, bible), bible, max_repair=2, threshold=6)
        scenes = conn.execute("SELECT * FROM scenes").fetchall()
        assert scenes[0]["status"] == "needs_human_review"
    finally:
        conn.close()


def test_malformed_director_output_raises_valueerror(tmp_path):
    conn, wid = _world(tmp_path / "m.db")
    try:
        router = ModelRouter(FakeAIClient(["not json at all"]),
                             Settings(openrouter_api_key="k", director_models=["d1"], rpm_limit=1000))
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        with pytest.raises(ValueError):
            generate_outline(wid, conn, router, Retriever(conn, bible))
    finally:
        conn.close()
