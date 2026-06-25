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
from app.ai.worldbuilder import generate_world_bible, load_world_bible, save_world_bible
from app.models.schemas import WorldBible
from tests.ai.fakes import FakeAIClient


def _world(db):
    init_db(db)
    conn = get_connection(db)
    data = generate_world(seed=11)
    w = data["world"]
    conn.execute("INSERT INTO worlds (id, seed, name, base_generated_version, current_tick, regions) "
                 "VALUES (?,?,?,?,?,?)",
                 (w["id"], w["seed"], w["name"], w["base_generated_version"], w["current_tick"],
                  json.dumps(w["regions"])))
    for s in data["structures"]:
        conn.execute("INSERT INTO structures (id, world_id, type, layer) VALUES (?,?,?,?)",
                     (s["id"], s["world_id"], s["type"], s["layer"]))
    conn.commit()
    return conn, w["id"]


def _settings():
    return Settings(openrouter_api_key="k", director_models=["d1"],
                    verifier_models=["v1"], rpm_limit=1000)


_BIBLE = json.dumps({
    "premise": "Aetherfall: a layered world where raw aether rains from the sky.",
    "aether_system": "Aether settles downward; mages bind it, but it corrupts the deep.",
    "the_fall": "When the Skyveil cracked, aether began falling unfiltered.",
    "history": "Three ages have passed since the Fall.",
    "layers": {"sky": "thin, aether-rich", "surface": "habitable belt", "underground": "mines",
               "deep": "corrupted", "ocean": "drowned ruins"},
    "peoples": "Valefolk farmers and the Deepwardens.",
    "factions_overview": "The Wardens seal the deep; the Gleaners harvest aether.",
    "themes": ["decay", "stewardship"],
    "tone": "Melancholy, grounded.",
})

_ACCEPT = json.dumps({"verdict": "accept",
                      "scores": {"completeness": 8, "conflict": 8, "coherence": 8}})


def test_generate_world_bible_persists(tmp_path):
    conn, wid = _world(tmp_path / "wb.db")
    try:
        router = ModelRouter(FakeAIClient([_BIBLE, _ACCEPT]), _settings())
        bible = generate_world_bible(wid, conn, router)
        assert bible.source == "ai" and bible.status == "draft"
        assert "aether" in bible.premise.lower()
        loaded = load_world_bible(conn, wid)
        assert loaded is not None
        assert loaded.layers["deep"] == "corrupted"
        assert loaded.themes == ["decay", "stewardship"]
    finally:
        conn.close()


def test_generate_world_bible_grounds_in_seed_facts(tmp_path):
    conn, wid = _world(tmp_path / "wb2.db")
    try:
        client = FakeAIClient([_BIBLE, _ACCEPT])
        generate_world_bible(wid, conn, ModelRouter(client, _settings()))
        _model, messages = client.calls[0]
        user_msg = messages[-1]["content"]
        assert "WORLD SEED FACTS" in user_msg
        assert "LAYERS PRESENT" in user_msg  # procedural layers fed to the model
    finally:
        conn.close()


_INCOMPLETE = json.dumps({
    "premise": "Aether rains from the sky.", "aether_system": "It settles downward.",
    "the_fall": "The sky cracked.", "history": "Ages passed.",
    "layers": {"sky": "thin", "surface": "habitable"},  # deep & ocean missing
    "peoples": "Valefolk.", "factions_overview": "Wardens vs Gleaners.",
    "themes": ["decay"], "tone": "Grim.",
})
_REVISE = json.dumps({"verdict": "revise", "scores": {"completeness": 3, "conflict": 7, "coherence": 7},
                      "fix_hints": ["deep layer is empty", "ocean layer is empty"]})


def test_verifier_repairs_incomplete_bible(tmp_path):
    conn, wid = _world(tmp_path / "wb_repair.db")
    try:
        # First draft has empty deep/ocean -> verifier asks to revise -> second draft is complete.
        client = FakeAIClient([_INCOMPLETE, _REVISE, _BIBLE, _ACCEPT])
        bible = generate_world_bible(wid, conn, ModelRouter(client, _settings()), max_repair=1)
        assert len(client.calls) == 4  # draft, verify, repair-draft, verify
        assert bible.layers["deep"] and bible.layers["ocean"]  # filled by the repair
        # The repair prompt must carry the verifier's fix-hints back to the author.
        repair_user = client.calls[2][1][-1]["content"]
        assert "ocean layer is empty" in repair_user
    finally:
        conn.close()


def test_incomplete_bible_always_has_five_layers(tmp_path):
    conn, wid = _world(tmp_path / "wb_layers.db")
    try:
        # Even if both author and verifier accept a thin draft, the schema is normalized.
        client = FakeAIClient([_INCOMPLETE, _ACCEPT])
        bible = generate_world_bible(wid, conn, ModelRouter(client, _settings()), max_repair=0)
        assert set(bible.layers) >= {"sky", "surface", "underground", "deep", "ocean"}
    finally:
        conn.close()


def test_non_json_draft_is_retried(tmp_path):
    conn, wid = _world(tmp_path / "wb_retry.db")
    try:
        # A free model emits prose first; the loop retries and recovers instead of 500ing.
        client = FakeAIClient(["sorry, here is the bible: ...", _BIBLE, _ACCEPT])
        bible = generate_world_bible(wid, conn, ModelRouter(client, _settings()), max_repair=1)
        assert bible.layers["deep"] == "corrupted"
        assert len(client.calls) == 3  # bad draft, good draft, verify
    finally:
        conn.close()


def test_malformed_bible_raises(tmp_path):
    conn, wid = _world(tmp_path / "wb3.db")
    try:
        router = ModelRouter(FakeAIClient(["not json at all"]), _settings())
        with pytest.raises(ValueError):
            generate_world_bible(wid, conn, router, max_repair=0)
    finally:
        conn.close()


def test_load_returns_none_when_absent(tmp_path):
    conn, wid = _world(tmp_path / "wb4.db")
    try:
        assert load_world_bible(conn, wid) is None
    finally:
        conn.close()


def test_user_edit_marks_human_and_round_trips(tmp_path):
    conn, wid = _world(tmp_path / "wb5.db")
    try:
        edited = WorldBible(world_id=wid, premise="User-revised premise.",
                            themes=["hope"], source="human", status="approved")
        save_world_bible(conn, edited)
        loaded = load_world_bible(conn, wid)
        assert loaded.premise == "User-revised premise."
        assert loaded.source == "human" and loaded.status == "approved"
    finally:
        conn.close()


def test_retriever_injects_bible_into_world_facts(tmp_path):
    conn, wid = _world(tmp_path / "wb6.db")
    try:
        generate_world_bible(wid, conn, ModelRouter(FakeAIClient([_BIBLE, _ACCEPT]), _settings()))
        sb = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        # Without world_id: no canon (backward compatible).
        plain = Retriever(conn, sb).world_facts()
        assert "WORLD BIBLE" not in plain
        # With world_id: canon is prepended ahead of procedural facts.
        grounded = Retriever(conn, sb, world_id=wid).world_facts()
        assert grounded.startswith("WORLD BIBLE")
        assert "aether" in grounded.lower()
    finally:
        conn.close()
