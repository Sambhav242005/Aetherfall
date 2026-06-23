import json
import httpx
from app.ai.ai_client import OpenRouterClient
from tests.ai.fakes import FakeAIClient


def test_fake_client_scripts_and_records():
    fake = FakeAIClient(["one", "two"])
    assert fake.chat([{"role": "user", "content": "hi"}], model="m1") == "one"
    assert fake.chat([{"role": "user", "content": "yo"}], model="m2", json_mode=True) == "two"
    assert [c[0] for c in fake.calls] == ["m1", "m2"]


def test_openrouter_client_builds_request(monkeypatch):
    captured = {}

    def fake_post(self, url, *, headers, json):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        req = httpx.Request("POST", url, headers=headers, json=json)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]}, request=req)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = OpenRouterClient(api_key="key", base_url="https://openrouter.ai/api/v1", timeout=5.0)
    out = client.chat([{"role": "user", "content": "hi"}], model="deepseek/deepseek-v3:free", json_mode=True)
    assert out == "hello"
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert captured["json"]["model"] == "deepseek/deepseek-v3:free"
    assert captured["json"]["response_format"] == {"type": "json_object"}
