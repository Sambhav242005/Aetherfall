from app.persistence.database import get_connection, init_db
from app.engine.world_generator import generate_world
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible
from app.ai.rag.retriever import Retriever, RetrievedContext


def _seed_world(db):
    init_db(db)
    conn = get_connection(db)
    data = generate_world(seed=42)
    wid = data["world"]["id"]
    for n in data["npcs"]:
        conn.execute("INSERT INTO npcs (id, name, faction_id, location_id, role, personality_tags, known_facts, secrets, power_profile, alive) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (n["id"], n["name"], n["faction_id"], n["location_id"], n["role"], "[]", "[]", "[]", "{}", 1))
    conn.commit()
    return conn, wid


def test_world_facts_filters_by_character(tmp_path):
    conn, _ = _seed_world(tmp_path / "w.db")
    try:
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        r = Retriever(conn, bible)
        facts = r.world_facts(character_ids=["npc_004"])
        assert "Lord Aldric" in facts
        assert "Elara" not in facts
    finally:
        conn.close()


def test_pack_respects_budget():
    ctx = RetrievedContext(world_facts="F" * 100, bible_slice="B" * 100)
    packed = ctx.pack(char_budget=120)
    assert len(packed) <= 120
    assert packed.startswith("F")


def test_retrieve_combines_world_and_bible(tmp_path):
    conn, wid = _seed_world(tmp_path / "w2.db")
    try:
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        bible.add_entry(wid, "scene", "s1", "the lake mutation spreads sickness to the farmers")
        r = Retriever(conn, bible)
        ctx = r.retrieve("lake sickness", k=1, character_ids=["npc_004"])
        assert "Lord Aldric" in ctx.world_facts
        assert "mutation" in ctx.bible_slice
    finally:
        conn.close()
