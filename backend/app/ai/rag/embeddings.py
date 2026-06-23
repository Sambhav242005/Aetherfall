from __future__ import annotations
import hashlib
import math
from typing import Protocol


class Embedder(Protocol):
    @property
    def dim(self) -> int: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic bag-of-hashed-tokens embedding. No external deps; for tests/offline."""

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in text.lower().split():
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class LocalEmbedder:
    """Production embeddings via sentence-transformers (lazy import)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self._model_name = model_name
        self._model = None

    def _ensure(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dim(self) -> int:
        return int(self._ensure().get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure()
        return [v.tolist() for v in model.encode(texts, normalize_embeddings=True)]
