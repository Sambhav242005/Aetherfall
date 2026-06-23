from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass
from app.ai.ai_client import ChatClient
from app.config import Settings


@dataclass
class RouterResult:
    content: str
    model: str


class ModelRouter:
    def __init__(self, client: ChatClient, settings: Settings) -> None:
        self._client = client
        self._s = settings
        self._calls: deque[float] = deque()

    def _models_for(self, tier: str) -> list[str]:
        return {
            "director": self._s.director_models,
            "worker": self._s.worker_models,
            "verifier": self._s.verifier_models,
        }[tier]

    def _respect_rpm(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] > 60.0:
            self._calls.popleft()
        if len(self._calls) >= self._s.rpm_limit:
            time.sleep(max(0.0, 60.0 - (now - self._calls[0])))
        self._calls.append(time.monotonic())

    def complete(self, tier: str, messages, *, json_mode=False, exclude_model=None, **kw) -> RouterResult:
        candidates = [m for m in self._models_for(tier) if m != exclude_model]
        last_err: Exception | None = None
        for model in candidates:
            self._respect_rpm()
            try:
                content = self._client.chat(messages, model, json_mode=json_mode, **kw)
                if content and content.strip():
                    return RouterResult(content=content, model=model)
                last_err = RuntimeError("empty response")
            except Exception as e:  # fall back to next model
                last_err = e
        raise RuntimeError(f"All {tier} models failed: {last_err}")
