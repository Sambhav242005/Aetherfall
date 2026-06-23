import importlib
from app import config


def test_defaults_load(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    importlib.reload(config)
    s = config.get_settings()
    assert s.openrouter_api_key == "test-key"
    assert s.openrouter_base_url.startswith("https://")
    assert s.director_models and s.worker_models and s.verifier_models
    assert s.rpm_limit == 20
    assert s.verifier_threshold == 6
    assert s.max_repair_attempts == 2
    assert s.embedding_dim == 64


def test_env_override(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("RPM_LIMIT", "5")
    importlib.reload(config)
    config.get_settings.cache_clear()
    assert config.get_settings().rpm_limit == 5
