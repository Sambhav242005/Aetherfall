import pytest
from app.config import Settings
from app.ai.model_router import ModelRouter
from tests.ai.fakes import FakeAIClient


def _settings():
    return Settings(openrouter_api_key="k",
                    director_models=["d1", "d2"],
                    worker_models=["w1"],
                    verifier_models=["v1", "v2"],
                    rpm_limit=1000)


def test_complete_uses_first_model():
    r = ModelRouter(FakeAIClient(["ok"]), _settings())
    res = r.complete("director", [{"role": "user", "content": "x"}])
    assert res.content == "ok" and res.model == "d1"


def test_exclude_model_for_cross_model_verification():
    fake = FakeAIClient(["judged"])
    r = ModelRouter(fake, _settings())
    res = r.complete("verifier", [{"role": "user", "content": "x"}], exclude_model="v1")
    assert res.model == "v2"


class FlakyClient:
    def __init__(self):
        self.calls = []
    def chat(self, messages, model, **kw):
        self.calls.append(model)
        if model == "d1":
            raise RuntimeError("rate limited")
        return "recovered"


def test_falls_back_on_error():
    r = ModelRouter(FlakyClient(), _settings())
    res = r.complete("director", [{"role": "user", "content": "x"}])
    assert res.model == "d2" and res.content == "recovered"


def test_falls_back_on_empty_response():
    class EmptyThenGood:
        def __init__(self):
            self.calls = []
        def chat(self, messages, model, **kw):
            self.calls.append(model)
            return "" if model == "d1" else "recovered"

    r = ModelRouter(EmptyThenGood(), _settings())
    res = r.complete("director", [{"role": "user", "content": "x"}])
    assert res.model == "d2" and res.content == "recovered"


def test_raises_when_all_fail():
    class Dead:
        def chat(self, *a, **k): raise RuntimeError("nope")
    r = ModelRouter(Dead(), _settings())
    with pytest.raises(RuntimeError):
        r.complete("worker", [{"role": "user", "content": "x"}])
