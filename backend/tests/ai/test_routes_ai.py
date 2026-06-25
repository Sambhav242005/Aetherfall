import json
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes_ai import get_router
from app.config import Settings
from app.ai.model_router import ModelRouter
from tests.ai.fakes import FakeAIClient

_OUTLINE = json.dumps({"title": "T", "premise": "p", "theme": "decay",
                       "beats": [{"act": 1, "summary": "dead fish at lake",
                                  "location_ids": ["struct_moonlake"],
                                  "character_ids": ["npc_001"], "faction_ids": []}]})
_VERDICT = json.dumps({"verdict": "accept", "scores": {"coherence": 8, "voice": 7, "grounding": 8}})


def test_generate_and_fetch_story():
    client = TestClient(app)
    world = client.post("/api/world/new", params={"seed": 99}).json()
    wid = world["world"]["id"]

    def fake_router():
        c = FakeAIClient([_OUTLINE, "scene prose at the lake", _VERDICT, "summary"])
        return ModelRouter(c, Settings(openrouter_api_key="k", director_models=["d1"],
                                       worker_models=["w1"], verifier_models=["v1"], rpm_limit=1000))

    app.dependency_overrides[get_router] = fake_router
    try:
        gen = client.post("/api/ai/story/generate", params={"world_id": wid}).json()
        assert gen["scene_count"] == 1
        story = client.get(f"/api/ai/story/{wid}").json()
        assert len(story["arcs"]) == 1 and len(story["scenes"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_validate_endpoint_rejects_bad_location():
    client = TestClient(app)
    client.post("/api/world/new", params={"seed": 1})
    body = {"id": "p1", "proposal_type": "scene", "payload": {"location_id": "struct_nowhere"}}
    resp = client.post("/api/ai/proposal/validate", json=body).json()
    assert resp["valid"] is False and resp["reasons"]


_BIBLE = json.dumps({
    "premise": "Aether rains from the sky onto a layered world.",
    "aether_system": "Aether settles downward and corrupts the deep.",
    "the_fall": "The Skyveil cracked.", "history": "Three ages have passed.",
    "layers": {"surface": "habitable belt"}, "peoples": "Valefolk farmers.",
    "factions_overview": "Wardens seal the deep; Gleaners harvest aether.",
    "themes": ["decay"], "tone": "Melancholy, grounded.",
})


def test_world_bible_generate_fetch_and_user_edit():
    client = TestClient(app)
    wid = client.post("/api/world/new", params={"seed": 7}).json()["world"]["id"]

    def fake_router():
        return ModelRouter(FakeAIClient([_BIBLE, _VERDICT]),
                           Settings(openrouter_api_key="k", director_models=["d1"],
                                    verifier_models=["v1"], rpm_limit=1000))

    app.dependency_overrides[get_router] = fake_router
    try:
        gen = client.post(f"/api/ai/world/{wid}/bible/generate").json()
        assert gen["source"] == "ai" and gen["status"] == "draft"
        assert "aether" in gen["premise"].lower()
    finally:
        app.dependency_overrides.clear()

    fetched = client.get(f"/api/ai/world/{wid}/bible").json()
    assert fetched["themes"] == ["decay"]

    # The user reviews and changes it; the edit is recorded as human-authored.
    edit = dict(fetched, premise="Player-revised premise.", status="approved")
    saved = client.put(f"/api/ai/world/{wid}/bible", json=edit).json()
    assert saved["source"] == "human" and saved["premise"] == "Player-revised premise."
    assert client.get(f"/api/ai/world/{wid}/bible").json()["status"] == "approved"


def test_world_bible_404_when_absent():
    client = TestClient(app)
    wid = client.post("/api/world/new", params={"seed": 8}).json()["world"]["id"]
    assert client.get(f"/api/ai/world/{wid}/bible").status_code == 404
