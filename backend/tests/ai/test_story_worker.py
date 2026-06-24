from app.config import Settings
from app.ai.model_router import ModelRouter
from app.ai.story_worker import draft_scene, revise_scene, summarize
from app.models.schemas import StoryBeat
from tests.ai.fakes import FakeAIClient


def _router(scripted):
    return ModelRouter(FakeAIClient(scripted),
                       Settings(openrouter_api_key="k", worker_models=["w1"], rpm_limit=1000))


def test_draft_returns_text_and_model():
    beat = StoryBeat(id="b1", arc_id="a1", act=1, order=0, summary="farmer finds dead fish")
    text, model = draft_scene(beat, "CONTEXT", _router(["A tense scene by the lake."]))
    assert "lake" in text and model == "w1"


def test_revise_includes_hints():
    fake = FakeAIClient(["revised text"])
    router = ModelRouter(fake, Settings(openrouter_api_key="k", worker_models=["w1"], rpm_limit=1000))
    out, _ = revise_scene("old", ["make Mira hostile"], "CONTEXT", router)
    assert out == "revised text"
    assert "make Mira hostile" in fake.calls[0][1][-1]["content"]


def test_summarize():
    assert summarize("long text", _router(["short summary"])) == "short summary"
