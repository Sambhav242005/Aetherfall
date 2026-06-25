from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    request_timeout: float = 60.0

    # NOTE: OpenRouter free-tier slugs change over time and are rate-limited PER MODEL,
    # so each tier spreads across providers (OpenAI/NVIDIA/Google/Qwen) for resilience.
    # JSON tiers (director/verifier) prefer gpt-oss-120b, which returns clean JSON;
    # the worker uses a different model so cross-model verification never self-excludes.
    director_models: list[str] = [
        "openai/gpt-oss-120b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
    ]
    worker_models: list[str] = [
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ]
    verifier_models: list[str] = [
        "openai/gpt-oss-120b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ]

    rpm_limit: int = 20
    verifier_threshold: int = 6
    max_repair_attempts: int = 2
    embedding_dim: int = 64


@lru_cache
def get_settings() -> Settings:
    return Settings()
