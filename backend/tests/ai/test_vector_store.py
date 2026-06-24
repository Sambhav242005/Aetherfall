from app.persistence.database import get_connection, init_db
from app.ai.rag.vector_store import VectorStore


def test_add_and_query_orders_by_similarity(tmp_path):
    db = tmp_path / "v.db"
    init_db(db)
    conn = get_connection(db)
    try:
        vs = VectorStore(conn, dim=3)
        vs.add("a", [1.0, 0.0, 0.0])
        vs.add("b", [0.0, 1.0, 0.0])
        vs.add("c", [0.9, 0.1, 0.0])
        results = vs.query([1.0, 0.0, 0.0], k=2)
        ids = [r[0] for r in results]
        assert ids[0] == "a"
        assert "c" in ids and "b" not in ids
        assert results[0][1] >= results[1][1]
    finally:
        conn.close()


def test_add_is_upsert(tmp_path):
    db = tmp_path / "v2.db"
    init_db(db)
    conn = get_connection(db)
    try:
        vs = VectorStore(conn, dim=2)
        vs.add("a", [1.0, 0.0])
        vs.add("a", [0.0, 1.0])
        assert len(vs.query([0.0, 1.0], k=5)) == 1
    finally:
        conn.close()
