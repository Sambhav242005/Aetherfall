from app.models.schemas import StoryArc, StoryBeat, Scene, BibleEntry, VerifierVerdict
from app.persistence.database import get_connection, init_db


def test_models_construct():
    arc = StoryArc(id="arc1", world_id="w1", title="T", premise="p", theme="decay")
    beat = StoryBeat(id="b1", arc_id="arc1", act=1, order=0, summary="s",
                     location_ids=["struct_moonlake"], character_ids=["npc_004"])
    scene = Scene(id="s1", beat_id="b1", title="First view")
    entry = BibleEntry(id="e1", world_id="w1", kind="scene", ref_id="s1", text="...")
    assert arc.beats == [] and beat.act == 1 and scene.status == "draft" and entry.kind == "scene"


def test_verdict_passed():
    v = VerifierVerdict(verdict="accept", scores={"coherence": 7, "voice": 6, "grounding": 8})
    assert v.passed(6) is True
    assert VerifierVerdict(verdict="accept", scores={"coherence": 5}).passed(6) is False
    assert VerifierVerdict(verdict="revise", scores={"coherence": 9}).passed(6) is False


def test_story_tables_created(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    conn = get_connection(db)
    try:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()
    assert {"story_arcs", "story_beats", "scenes", "bible_entries", "bible_vectors"} <= names
