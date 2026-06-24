from app.persistence.database import get_connection, init_db
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible


def _bible(db):
    init_db(db)
    conn = get_connection(db)
    emb = HashEmbedder(dim=64)
    return conn, StoryBible(conn, emb, VectorStore(conn, dim=emb.dim))


def test_add_and_search(tmp_path):
    conn, bible = _bible(tmp_path / "b.db")
    try:
        bible.add_entry("w1", "scene", "s1", "the moonlake glows with cursed magic and dead fish")
        bible.add_entry("w1", "scene", "s2", "merchants trade grain in the busy town market")
        hits = bible.search("cursed lake magic", k=1)
        assert len(hits) == 1 and hits[0].ref_id == "s1"
    finally:
        conn.close()


def test_all_entries(tmp_path):
    conn, bible = _bible(tmp_path / "b2.db")
    try:
        bible.add_entry("w1", "arc", "a1", "premise")
        bible.add_entry("w1", "beat", "b1", "beat summary")
        assert {e.ref_id for e in bible.all_entries("w1")} == {"a1", "b1"}
    finally:
        conn.close()
