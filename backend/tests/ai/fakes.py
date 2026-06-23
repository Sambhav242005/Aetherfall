from __future__ import annotations


class FakeAIClient:
    def __init__(self, scripted: list[str]) -> None:
        self._scripted = list(scripted)
        self._i = 0
        self.calls: list[tuple[str, list[dict]]] = []

    def chat(self, messages, model, *, json_mode=False, temperature=0.7, max_tokens=2048):
        self.calls.append((model, messages))
        if self._i >= len(self._scripted):
            raise IndexError("FakeAIClient ran out of scripted responses")
        out = self._scripted[self._i]
        self._i += 1
        return out
