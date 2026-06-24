import os
import pytest
from app.config import get_settings
from app.ai.ai_client import OpenRouterClient

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE_AI") != "1", reason="live AI test disabled")


def test_real_free_model_responds():
    s = get_settings()
    assert s.openrouter_api_key, "set OPENROUTER_API_KEY"
    client = OpenRouterClient(s.openrouter_api_key, s.openrouter_base_url, s.request_timeout)
    out = client.chat([{"role": "user", "content": "Reply with the single word: ok"}],
                      model=s.worker_models[0], max_tokens=10)
    assert out.strip()
