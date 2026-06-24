import json
from app.config import Settings
from app.ai.model_router import ModelRouter
from app.ai.story_verifier import verify_scene
from tests.ai.fakes import FakeAIClient


def _router(scripted):
    return ModelRouter(FakeAIClient(scripted),
                       Settings(openrouter_api_key="k",
                                verifier_models=["v1", "v2"], rpm_limit=1000))


def test_parses_accept_verdict():
    payload = json.dumps({"verdict": "accept",
                          "scores": {"coherence": 8, "voice": 7, "grounding": 9},
                          "issues": [], "fix_hints": []})
    v = verify_scene("scene", "ctx", _router([payload]), generator_model="d1", threshold=6)
    assert v.passed(6) is True


def test_cross_model_excludes_generator():
    payload = json.dumps({"verdict": "accept", "scores": {"coherence": 7}})
    fake = FakeAIClient([payload])
    router = ModelRouter(fake, Settings(openrouter_api_key="k",
                                        verifier_models=["v1", "v2"], rpm_limit=1000))
    verify_scene("scene", "ctx", router, generator_model="v1", threshold=6)
    assert fake.calls[0][0] == "v2"  # skipped the generator's model


def test_unparseable_is_reject():
    v = verify_scene("scene", "ctx", _router(["not json at all"]),
                     generator_model="d1", threshold=6)
    assert v.verdict == "reject"
