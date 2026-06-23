from __future__ import annotations
from typing import Protocol
import httpx


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]], model: str, *,
             json_mode: bool = False, temperature: float = 0.7,
             max_tokens: int = 2048) -> str: ...


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str, timeout: float) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def chat(self, messages, model, *, json_mode=False, temperature=0.7, max_tokens=2048):
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(f"{self._base_url}/chat/completions",
                               headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
