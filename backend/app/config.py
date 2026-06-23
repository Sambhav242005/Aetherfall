from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    request_timeout: float = 60.0

    director_models: list[str] = [
        "deepseek/deepseek-v3:free",
        "qwen/qwen3-235b-a22b:free",
    ]
    worker_models: list[str] = [
        "meta-llama/llama-4-scout:free",
        "google/gemma-3-27b:free",
    ]
    verifier_models: list[str] = [
        "qwen/qwen3-235b-a22b:free",
        "deepseek/deepseek-r1:free",
    ]

    rpm_limit: int = 20
    verifier_threshold: int = 6
    max_repair_attempts: int = 2
    embedding_dim: int = 64


@lru_cache
def get_settings() -> Settings:
    return Settings()
