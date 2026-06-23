# Stage 1: Story Director + RAG + Verification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an AI layer that generates a deep, context-exceeding, internally-consistent, world-grounded story for Riverfall Valley using tiered free OpenRouter models, RAG memory, and two-layer (deterministic + cross-model LLM) verification.

**Architecture:** Hierarchical generation — a strong Director model outlines acts/beats; fast Worker models draft and summarize scenes; a RAG store (local embeddings + same-DB vector table) feeds each call a bounded, retrieved slice of a growing Story Bible plus canonical world facts; every output passes a deterministic Validator then a cross-model LLM Verifier with a bounded repair loop before becoming canonical.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, `pydantic-settings`, `httpx` (OpenRouter), NumPy (vector cosine), `sentence-transformers` (production embeddings, lazy), SQLite, pytest. Companion spec: `docs/superpowers/specs/2026-06-23-stage1-story-rag-design.md`.

## Global Constraints

- All paths are relative to repo root `C:\Users\NPC\Desktop\Aetherfall`; backend code lives in `backend/`. Run all `pytest` commands from `backend/` (imports are `from app...`).
- **No network in tests.** Every test uses `FakeAIClient` + `HashEmbedder`. Only the optional live smoke test (gated by env `RUN_LIVE_AI=1`) may hit the network.
- AI output that drives the engine MUST be a strict-JSON `AIProposal`; free-form text allowed only for display dialogue.
- AI MUST NOT write canonical state directly — only the validated approval path persists records.
- `OPENROUTER_API_KEY` comes from env/`.env` via `pydantic-settings`. Never hardcode or log it.
- Free model IDs shift; all model ids live in `config.py` as ordered fallback lists, never inline.
- Verifier MUST use a different model than the one that generated the text (cross-model).
- Preserve existing conventions: raw `sqlite3` via `get_connection`/`init_db`, JSON stored as TEXT columns, `APIRouter` registered in `main.py`, Pydantic models in `models/schemas.py`.
- **Repo is not yet a git repo.** Before Task 1, run `git init` in repo root (commit steps assume git exists). If the team prefers no VCS, treat each "Commit" step as a checkpoint and skip the git command.

---

### Task 1: Project config & settings

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (pydantic-settings) with fields `openrouter_api_key: str`, `openrouter_base_url: str`, `director_models: list[str]`, `worker_models: list[str]`, `verifier_models: list[str]`, `rpm_limit: int`, `verifier_threshold: int`, `max_repair_attempts: int`, `embedding_dim: int`, `request_timeout: float`. Function `get_settings() -> Settings` (cached).

- [ ] **Step 1: Add dependencies**

Append to `backend/requirements.txt`:
```
pydantic-settings>=2.1.0
numpy>=1.26.0
sentence-transformers>=2.7.0
```
Then run: `cd backend && pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_config.py`:
```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 4: Write minimal implementation**

Create `backend/app/config.py`:
```python
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
```

Create `backend/.env.example`:
```
OPENROUTER_API_KEY=sk-or-...your-key-here...
RPM_LIMIT=20
```

- [ ] **Step 5: Run tests & commit**

Run: `cd backend && python -m pytest tests/test_config.py -v` → Expected: PASS.
```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
echo "backend/.env" >> .gitignore
git add backend/app/config.py backend/.env.example backend/requirements.txt backend/tests/test_config.py .gitignore
git commit -m "feat(ai): add settings/config for OpenRouter tiers and RAG"
```

---

### Task 2: Story & RAG schemas + DB tables

**Files:**
- Modify: `backend/app/models/schemas.py` (append)
- Modify: `backend/app/persistence/database.py` (extend `init_db` script)
- Test: `backend/tests/test_story_schema.py`

**Interfaces:**
- Produces Pydantic models:
  - `StoryArc(id: str, world_id: str, title: str, premise: str, theme: str, beats: list[str] = [])`
  - `StoryBeat(id: str, arc_id: str, act: int, order: int, summary: str, location_ids: list[str] = [], character_ids: list[str] = [], faction_ids: list[str] = [], status: str = "draft")`
  - `Scene(id: str, beat_id: str, title: str, prose: str = "", dialogue: list[dict] = [], storyboard_card_id: str | None = None, revealed_information: list[str] = [], status: str = "draft")`
  - `BibleEntry(id: str, world_id: str, kind: str, ref_id: str, text: str)`
  - `VerifierVerdict(verdict: str, scores: dict[str, int] = {}, issues: list[str] = [], fix_hints: list[str] = [])` with method `passed(self, threshold: int) -> bool`.
- Produces DB tables: `story_arcs`, `story_beats`, `scenes`, `bible_entries`, `bible_vectors`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_story_schema.py`:
```python
from app.models.schemas import StoryArc, StoryBeat, Scene, BibleEntry, VerifierVerdict
from app.persistence.database import get_connection, init_db


def test_models_construct():
    arc = StoryArc(id="arc1", world_id="w1", title="T", premise="p", theme="decay")
    beat = StoryBeat(id="b1", arc_id="arc1", act=1, order=0, summary="s",
                     location_ids=["struct_moonlake"], character_ids=["npc_004"])
    scene = Scene(id="s1", beat_id="b1", title="First view")
    entry = BibleEntry(id="e1", world_id="w1", kind="scene", ref_id="s1", text="...")
    assert arc.beats == [] and beat.act == 1 and scene.status == "draft" and entry.kind == "scene"


def test_verdict_passed():
    v = VerifierVerdict(verdict="accept", scores={"coherence": 7, "voice": 6, "grounding": 8})
    assert v.passed(6) is True
    assert VerifierVerdict(verdict="accept", scores={"coherence": 5}).passed(6) is False
    assert VerifierVerdict(verdict="revise", scores={"coherence": 9}).passed(6) is False


def test_story_tables_created(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    conn = get_connection(db)
    try:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()
    assert {"story_arcs", "story_beats", "scenes", "bible_entries", "bible_vectors"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_story_schema.py -v`
Expected: FAIL with `ImportError: cannot import name 'StoryArc'`.

- [ ] **Step 3: Append schemas**

Append to `backend/app/models/schemas.py`:
```python
class StoryArc(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    world_id: str
    title: str
    premise: str
    theme: str
    beats: list[str] = Field(default_factory=list)


class StoryBeat(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    arc_id: str
    act: int
    order: int
    summary: str
    location_ids: list[str] = Field(default_factory=list)
    character_ids: list[str] = Field(default_factory=list)
    faction_ids: list[str] = Field(default_factory=list)
    status: str = "draft"


class Scene(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    beat_id: str
    title: str
    prose: str = ""
    dialogue: list[dict[str, Any]] = Field(default_factory=list)
    storyboard_card_id: str | None = None
    revealed_information: list[str] = Field(default_factory=list)
    status: str = "draft"


class BibleEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    world_id: str
    kind: str
    ref_id: str
    text: str


class VerifierVerdict(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    verdict: str
    scores: dict[str, int] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    fix_hints: list[str] = Field(default_factory=list)

    def passed(self, threshold: int) -> bool:
        if self.verdict != "accept":
            return False
        return all(v >= threshold for v in self.scores.values()) if self.scores else False
```

- [ ] **Step 4: Extend the DB schema**

In `backend/app/persistence/database.py`, inside the `conn.executescript("""...""")` string, append these tables before the closing `"""`:
```sql
            CREATE TABLE IF NOT EXISTS story_arcs (
                id TEXT PRIMARY KEY,
                world_id TEXT NOT NULL,
                title TEXT NOT NULL,
                premise TEXT NOT NULL DEFAULT '',
                theme TEXT NOT NULL DEFAULT '',
                beats TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS story_beats (
                id TEXT PRIMARY KEY,
                arc_id TEXT NOT NULL,
                act INTEGER NOT NULL DEFAULT 1,
                "order" INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL DEFAULT '',
                location_ids TEXT NOT NULL DEFAULT '[]',
                character_ids TEXT NOT NULL DEFAULT '[]',
                faction_ids TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft'
            );

            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                beat_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                prose TEXT NOT NULL DEFAULT '',
                dialogue TEXT NOT NULL DEFAULT '[]',
                storyboard_card_id TEXT,
                revealed_information TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft'
            );

            CREATE TABLE IF NOT EXISTS bible_entries (
                id TEXT PRIMARY KEY,
                world_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                ref_id TEXT NOT NULL,
                text TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS bible_vectors (
                entry_id TEXT PRIMARY KEY,
                dim INTEGER NOT NULL,
                vector TEXT NOT NULL
            );
```

- [ ] **Step 5: Run tests & commit**

Run: `cd backend && python -m pytest tests/test_story_schema.py -v` → Expected: PASS.
```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/models/schemas.py backend/app/persistence/database.py backend/tests/test_story_schema.py
git commit -m "feat(ai): add story/RAG schemas and DB tables"
```

---

### Task 3: OpenRouter client + ChatClient protocol + FakeAIClient

**Files:**
- Create: `backend/app/ai/__init__.py` (empty)
- Create: `backend/app/ai/ai_client.py`
- Create: `backend/tests/ai/__init__.py` (empty)
- Create: `backend/tests/ai/fakes.py`
- Test: `backend/tests/ai/test_ai_client.py`

**Interfaces:**
- Produces `ChatClient` Protocol: `chat(self, messages: list[dict[str, str]], model: str, *, json_mode: bool = False, temperature: float = 0.7, max_tokens: int = 2048) -> str`.
- Produces `OpenRouterClient(api_key: str, base_url: str, timeout: float)` implementing `ChatClient` via `httpx`.
- Produces `FakeAIClient(scripted: list[str])` implementing `ChatClient`; pops responses in order; records `.calls: list[tuple[str, list[dict]]]` (model, messages); raises `IndexError` if exhausted.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/__init__.py` (empty) and `backend/tests/ai/test_ai_client.py`:
```python
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
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = OpenRouterClient(api_key="key", base_url="https://openrouter.ai/api/v1", timeout=5.0)
    out = client.chat([{"role": "user", "content": "hi"}], model="deepseek/deepseek-v3:free", json_mode=True)
    assert out == "hello"
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert captured["json"]["model"] == "deepseek/deepseek-v3:free"
    assert captured["json"]["response_format"] == {"type": "json_object"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_ai_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/__init__.py` (empty file).

Create `backend/app/ai/ai_client.py`:
```python
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
```

Create `backend/tests/ai/fakes.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_ai_client.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/__init__.py backend/app/ai/ai_client.py backend/tests/ai/
git commit -m "feat(ai): add OpenRouter client, ChatClient protocol, FakeAIClient"
```

---

### Task 4: Model router (tiered fallback + RPM limiter + cross-model)

**Files:**
- Create: `backend/app/ai/model_router.py`
- Test: `backend/tests/ai/test_model_router.py`

**Interfaces:**
- Consumes: `ChatClient`, `Settings`.
- Produces:
  - `RouterResult(content: str, model: str)` (dataclass).
  - `ModelRouter(client: ChatClient, settings: Settings)` with:
    - `complete(self, tier: str, messages: list[dict], *, json_mode: bool = False, exclude_model: str | None = None, **kw) -> RouterResult` — picks first model in the tier list (skipping `exclude_model`), advances to next on exception; raises `RuntimeError` if all fail.
    - `_models_for(self, tier: str) -> list[str]` — `"director"|"worker"|"verifier"` → settings list.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_model_router.py`:
```python
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


def test_raises_when_all_fail():
    class Dead:
        def chat(self, *a, **k): raise RuntimeError("nope")
    r = ModelRouter(Dead(), _settings())
    with pytest.raises(RuntimeError):
        r.complete("worker", [{"role": "user", "content": "x"}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_model_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.model_router'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/model_router.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_model_router.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/model_router.py backend/tests/ai/test_model_router.py
git commit -m "feat(ai): tiered model router with fallback, RPM limit, cross-model exclude"
```

---

### Task 5: Embeddings (deterministic + lazy local)

**Files:**
- Create: `backend/app/ai/rag/__init__.py` (empty)
- Create: `backend/app/ai/rag/embeddings.py`
- Test: `backend/tests/ai/test_embeddings.py`

**Interfaces:**
- Produces `Embedder` Protocol: `embed(self, texts: list[str]) -> list[list[float]]`; property `dim: int`.
- Produces `HashEmbedder(dim: int = 64)` — deterministic, no deps (used in all tests).
- Produces `LocalEmbedder(model_name: str = "BAAI/bge-small-en-v1.5")` — lazy-imports `sentence-transformers` in `embed()`/`dim`.

- [ ] **Step 1: Write the failing test**

Create `backend/app/ai/rag/__init__.py` (empty) and `backend/tests/ai/test_embeddings.py`:
```python
import math
from app.ai.rag.embeddings import HashEmbedder


def test_deterministic_and_dim():
    e = HashEmbedder(dim=32)
    a = e.embed(["hello world"])[0]
    b = e.embed(["hello world"])[0]
    assert a == b
    assert len(a) == 32 == e.dim


def test_unit_norm_and_distinct():
    e = HashEmbedder(dim=16)
    v = e.embed(["a"])[0]
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)
    assert e.embed(["a"]) != e.embed(["completely different text"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_embeddings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.rag.embeddings'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/rag/embeddings.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_embeddings.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/rag/__init__.py backend/app/ai/rag/embeddings.py backend/tests/ai/test_embeddings.py
git commit -m "feat(rag): deterministic HashEmbedder + lazy LocalEmbedder"
```

---

### Task 6: Vector store (same-DB table + NumPy cosine)

**Files:**
- Create: `backend/app/ai/rag/vector_store.py`
- Test: `backend/tests/ai/test_vector_store.py`

**Interfaces:**
- Consumes: `sqlite3.Connection` (from `get_connection`), `bible_vectors` table (Task 2).
- Produces `VectorStore(conn: sqlite3.Connection, dim: int)`:
  - `add(self, entry_id: str, vector: list[float]) -> None` (upsert).
  - `query(self, vector: list[float], k: int = 5) -> list[tuple[str, float]]` — returns `(entry_id, cosine_score)` sorted desc.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_vector_store.py`:
```python
from app.persistence.database import get_connection, init_db
from app.ai.rag.vector_store import VectorStore


def test_add_and_query_orders_by_similarity(tmp_path):
    db = tmp_path / "v.db"
    init_db(db)
    conn = get_connection(db)
    try:
        vs = VectorStore(conn, dim=3)
        vs.add("a", [1.0, 0.0, 0.0])
        vs.add("b", [0.0, 1.0, 0.0])
        vs.add("c", [0.9, 0.1, 0.0])
        results = vs.query([1.0, 0.0, 0.0], k=2)
        ids = [r[0] for r in results]
        assert ids[0] == "a"
        assert "c" in ids and "b" not in ids
        assert results[0][1] >= results[1][1]
    finally:
        conn.close()


def test_add_is_upsert(tmp_path):
    db = tmp_path / "v2.db"
    init_db(db)
    conn = get_connection(db)
    try:
        vs = VectorStore(conn, dim=2)
        vs.add("a", [1.0, 0.0])
        vs.add("a", [0.0, 1.0])
        assert len(vs.query([0.0, 1.0], k=5)) == 1
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_vector_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.rag.vector_store'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/rag/vector_store.py`:
```python
from __future__ import annotations
import json
import sqlite3
import numpy as np


class VectorStore:
    def __init__(self, conn: sqlite3.Connection, dim: int) -> None:
        self._conn = conn
        self._dim = dim

    def add(self, entry_id: str, vector: list[float]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO bible_vectors (entry_id, dim, vector) VALUES (?, ?, ?)",
            (entry_id, self._dim, json.dumps(vector)),
        )
        self._conn.commit()

    def query(self, vector: list[float], k: int = 5) -> list[tuple[str, float]]:
        rows = self._conn.execute("SELECT entry_id, vector FROM bible_vectors").fetchall()
        if not rows:
            return []
        q = np.asarray(vector, dtype=float)
        qn = np.linalg.norm(q) or 1.0
        scored: list[tuple[str, float]] = []
        for row in rows:
            v = np.asarray(json.loads(row["vector"]), dtype=float)
            vn = np.linalg.norm(v) or 1.0
            scored.append((row["entry_id"], float(np.dot(q, v) / (qn * vn))))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_vector_store.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/rag/vector_store.py backend/tests/ai/test_vector_store.py
git commit -m "feat(rag): same-DB vector store with NumPy cosine search"
```

---

### Task 7: Story Bible (write/read + embed)

**Files:**
- Create: `backend/app/ai/rag/story_bible.py`
- Test: `backend/tests/ai/test_story_bible.py`

**Interfaces:**
- Consumes: `sqlite3.Connection`, `Embedder` (Task 5), `VectorStore` (Task 6), `BibleEntry` (Task 2), `bible_entries` table.
- Produces `StoryBible(conn, embedder: Embedder, store: VectorStore)`:
  - `add_entry(self, world_id: str, kind: str, ref_id: str, text: str) -> BibleEntry` — writes row + embedding; entry id = `f"bible_{kind}_{ref_id}"`.
  - `search(self, query: str, k: int = 5) -> list[BibleEntry]` — vector search then hydrate rows.
  - `all_entries(self, world_id: str) -> list[BibleEntry]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_story_bible.py`:
```python
from app.persistence.database import get_connection, init_db
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible


def _bible(db):
    init_db(db)
    conn = get_connection(db)
    emb = HashEmbedder(dim=64)
    return conn, StoryBible(conn, emb, VectorStore(conn, dim=emb.dim))


def test_add_and_search(tmp_path):
    conn, bible = _bible(tmp_path / "b.db")
    try:
        bible.add_entry("w1", "scene", "s1", "the moonlake glows with cursed magic and dead fish")
        bible.add_entry("w1", "scene", "s2", "merchants trade grain in the busy town market")
        hits = bible.search("cursed lake magic", k=1)
        assert len(hits) == 1 and hits[0].ref_id == "s1"
    finally:
        conn.close()


def test_all_entries(tmp_path):
    conn, bible = _bible(tmp_path / "b2.db")
    try:
        bible.add_entry("w1", "arc", "a1", "premise")
        bible.add_entry("w1", "beat", "b1", "beat summary")
        assert {e.ref_id for e in bible.all_entries("w1")} == {"a1", "b1"}
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_story_bible.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.rag.story_bible'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/rag/story_bible.py`:
```python
from __future__ import annotations
import sqlite3
from app.models.schemas import BibleEntry
from app.ai.rag.embeddings import Embedder
from app.ai.rag.vector_store import VectorStore


class StoryBible:
    def __init__(self, conn: sqlite3.Connection, embedder: Embedder, store: VectorStore) -> None:
        self._conn = conn
        self._embedder = embedder
        self._store = store

    def add_entry(self, world_id: str, kind: str, ref_id: str, text: str) -> BibleEntry:
        entry = BibleEntry(id=f"bible_{kind}_{ref_id}", world_id=world_id,
                           kind=kind, ref_id=ref_id, text=text)
        self._conn.execute(
            "INSERT OR REPLACE INTO bible_entries (id, world_id, kind, ref_id, text) VALUES (?, ?, ?, ?, ?)",
            (entry.id, entry.world_id, entry.kind, entry.ref_id, entry.text),
        )
        self._conn.commit()
        self._store.add(entry.id, self._embedder.embed([text])[0])
        return entry

    def _row_to_entry(self, row) -> BibleEntry:
        return BibleEntry(id=row["id"], world_id=row["world_id"], kind=row["kind"],
                          ref_id=row["ref_id"], text=row["text"])

    def search(self, query: str, k: int = 5) -> list[BibleEntry]:
        vec = self._embedder.embed([query])[0]
        hits = self._store.query(vec, k=k)
        out: list[BibleEntry] = []
        for entry_id, _score in hits:
            row = self._conn.execute("SELECT * FROM bible_entries WHERE id = ?", (entry_id,)).fetchone()
            if row is not None:
                out.append(self._row_to_entry(row))
        return out

    def all_entries(self, world_id: str) -> list[BibleEntry]:
        rows = self._conn.execute("SELECT * FROM bible_entries WHERE world_id = ?", (world_id,)).fetchall()
        return [self._row_to_entry(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_story_bible.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/rag/story_bible.py backend/tests/ai/test_story_bible.py
git commit -m "feat(rag): StoryBible write/read with embedding"
```

---

### Task 8: Retriever + token-budget context packer

**Files:**
- Create: `backend/app/ai/rag/retriever.py`
- Test: `backend/tests/ai/test_retriever.py`

**Interfaces:**
- Consumes: `sqlite3.Connection`, `StoryBible` (Task 7), world tables (`structures`, `npcs`, `factions`).
- Produces:
  - `RetrievedContext(world_facts: str, bible_slice: str)` (dataclass) with `pack(self, char_budget: int) -> str` — concatenates `world_facts` then `bible_slice`, truncating to budget (world facts kept first).
  - `Retriever(conn, bible: StoryBible)`:
    - `world_facts(self, location_ids: list[str] | None = None, character_ids: list[str] | None = None, faction_ids: list[str] | None = None) -> str` — formatted lines from DB.
    - `retrieve(self, query: str, *, k: int = 5, location_ids=None, character_ids=None, faction_ids=None) -> RetrievedContext`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_retriever.py`:
```python
from app.persistence.database import get_connection, init_db
from app.engine.world_generator import generate_world
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible
from app.ai.rag.retriever import Retriever, RetrievedContext


def _seed_world(db):
    init_db(db)
    conn = get_connection(db)
    data = generate_world(seed=42)
    wid = data["world"]["id"]
    for n in data["npcs"]:
        conn.execute("INSERT INTO npcs (id, name, faction_id, location_id, role, personality_tags, known_facts, secrets, power_profile, alive) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (n["id"], n["name"], n["faction_id"], n["location_id"], n["role"], "[]", "[]", "[]", "{}", 1))
    conn.commit()
    return conn, wid


def test_world_facts_filters_by_character(tmp_path):
    conn, _ = _seed_world(tmp_path / "w.db")
    try:
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        r = Retriever(conn, bible)
        facts = r.world_facts(character_ids=["npc_004"])
        assert "Lord Aldric" in facts
        assert "Elara" not in facts
    finally:
        conn.close()


def test_pack_respects_budget():
    ctx = RetrievedContext(world_facts="F" * 100, bible_slice="B" * 100)
    packed = ctx.pack(char_budget=120)
    assert len(packed) <= 120
    assert packed.startswith("F")


def test_retrieve_combines_world_and_bible(tmp_path):
    conn, wid = _seed_world(tmp_path / "w2.db")
    try:
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        bible.add_entry(wid, "scene", "s1", "the lake mutation spreads sickness to the farmers")
        r = Retriever(conn, bible)
        ctx = r.retrieve("lake sickness", k=1, character_ids=["npc_004"])
        assert "Lord Aldric" in ctx.world_facts
        assert "mutation" in ctx.bible_slice
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_retriever.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.rag.retriever'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/rag/retriever.py`:
```python
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from app.ai.rag.story_bible import StoryBible


@dataclass
class RetrievedContext:
    world_facts: str
    bible_slice: str

    def pack(self, char_budget: int) -> str:
        combined = self.world_facts
        remaining = char_budget - len(combined)
        if remaining > 0 and self.bible_slice:
            combined = combined + ("\n" if combined else "") + self.bible_slice
        return combined[:char_budget]


class Retriever:
    def __init__(self, conn: sqlite3.Connection, bible: StoryBible) -> None:
        self._conn = conn
        self._bible = bible

    def _rows(self, table: str, ids: list[str] | None) -> list:
        if ids is None:
            return self._conn.execute(f"SELECT * FROM {table}").fetchall()
        if not ids:
            return []
        marks = ",".join("?" for _ in ids)
        return self._conn.execute(f"SELECT * FROM {table} WHERE id IN ({marks})", ids).fetchall()

    def world_facts(self, location_ids=None, character_ids=None, faction_ids=None) -> str:
        lines: list[str] = []
        for s in self._rows("structures", location_ids):
            lines.append(f"LOCATION {s['id']}: {s['type']} (layer {s['layer']})")
        for n in self._rows("npcs", character_ids):
            lines.append(f"CHARACTER {n['id']}: {n['name']}, {n['role']}, at {n['location_id']}")
        for f in self._rows("factions", faction_ids):
            lines.append(f"FACTION {f['id']}: {f['name']}")
        return "\n".join(lines)

    def retrieve(self, query, *, k=5, location_ids=None, character_ids=None, faction_ids=None) -> RetrievedContext:
        facts = self.world_facts(location_ids, character_ids, faction_ids)
        entries = self._bible.search(query, k=k)
        bible_slice = "\n".join(f"[{e.kind}:{e.ref_id}] {e.text}" for e in entries)
        return RetrievedContext(world_facts=facts, bible_slice=bible_slice)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_retriever.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/rag/retriever.py backend/tests/ai/test_retriever.py
git commit -m "feat(rag): hybrid retriever + token-budget context packer"
```

---

### Task 9: Deterministic validator (hard gate)

**Files:**
- Create: `backend/app/ai/ai_validator.py`
- Test: `backend/tests/ai/test_ai_validator.py`

**Interfaces:**
- Consumes: `sqlite3.Connection`, `AIProposal` (existing schema), world tables.
- Produces `validate_proposal(proposal: AIProposal, conn: sqlite3.Connection) -> list[str]` — returns rejection reasons; empty list = valid. Checks: referenced ids exist (`structures`/`npcs`/`factions`), payload declares no forbidden mutation keys (`inventory`, `damage`, `death`, `ownership`, `quest_completion`, `map_geometry`), and any `location_id`/`character_ids`/`faction_ids` in payload exist.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_ai_validator.py`:
```python
from app.persistence.database import get_connection, init_db
from app.engine.world_generator import generate_world
from app.models.schemas import AIProposal
from app.ai.ai_validator import validate_proposal


def _world(db):
    init_db(db)
    conn = get_connection(db)
    data = generate_world(seed=7)
    for n in data["npcs"]:
        conn.execute("INSERT INTO npcs (id, name, faction_id, location_id, role) VALUES (?,?,?,?,?)",
                     (n["id"], n["name"], n["faction_id"], n["location_id"], n["role"]))
    for s in data["structures"]:
        conn.execute("INSERT INTO structures (id, world_id, type, layer) VALUES (?,?,?,?)",
                     (s["id"], s["world_id"], s["type"], s["layer"]))
    conn.commit()
    return conn


def test_accepts_grounded_proposal(tmp_path):
    conn = _world(tmp_path / "v.db")
    try:
        p = AIProposal(id="p1", proposal_type="scene",
                       payload={"location_id": "struct_moonlake", "character_ids": ["npc_004"]})
        assert validate_proposal(p, conn) == []
    finally:
        conn.close()


def test_rejects_missing_location(tmp_path):
    conn = _world(tmp_path / "v2.db")
    try:
        p = AIProposal(id="p2", proposal_type="scene", payload={"location_id": "struct_atlantis"})
        reasons = validate_proposal(p, conn)
        assert any("struct_atlantis" in r for r in reasons)
    finally:
        conn.close()


def test_rejects_state_mutation(tmp_path):
    conn = _world(tmp_path / "v3.db")
    try:
        p = AIProposal(id="p3", proposal_type="scene",
                       payload={"location_id": "struct_moonlake", "death": "npc_004"})
        reasons = validate_proposal(p, conn)
        assert any("death" in r for r in reasons)
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_ai_validator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.ai_validator'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/ai_validator.py`:
```python
from __future__ import annotations
import sqlite3
from app.models.schemas import AIProposal

FORBIDDEN_KEYS = {"inventory", "damage", "death", "ownership", "quest_completion", "map_geometry"}


def _exists(conn: sqlite3.Connection, table: str, id_: str) -> bool:
    return conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (id_,)).fetchone() is not None


def validate_proposal(proposal: AIProposal, conn: sqlite3.Connection) -> list[str]:
    reasons: list[str] = []
    payload = proposal.payload or {}

    for key in FORBIDDEN_KEYS:
        if key in payload:
            reasons.append(f"proposal attempts forbidden state mutation: '{key}'")

    loc = payload.get("location_id")
    if loc is not None and not _exists(conn, "structures", loc):
        reasons.append(f"location does not exist: {loc}")

    for cid in payload.get("character_ids", []) or []:
        if not _exists(conn, "npcs", cid):
            reasons.append(f"character does not exist: {cid}")

    for fid in payload.get("faction_ids", []) or []:
        if not _exists(conn, "factions", fid):
            reasons.append(f"faction does not exist: {fid}")

    return reasons
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_ai_validator.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/ai_validator.py backend/tests/ai/test_ai_validator.py
git commit -m "feat(ai): deterministic proposal validator (hard gate)"
```

---

### Task 10: Cross-model verifier (LLM judge)

**Files:**
- Create: `backend/app/ai/story_verifier.py`
- Test: `backend/tests/ai/test_story_verifier.py`

**Interfaces:**
- Consumes: `ModelRouter` (Task 4), `VerifierVerdict` (Task 2).
- Produces `verify_scene(scene_text: str, packed_context: str, router: ModelRouter, *, generator_model: str, threshold: int) -> VerifierVerdict` — calls `router.complete("verifier", ..., json_mode=True, exclude_model=generator_model)` (cross-model), parses JSON into `VerifierVerdict`; on parse failure returns `VerifierVerdict(verdict="reject", issues=["unparseable verifier output"])`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_story_verifier.py`:
```python
import json
from app.config import Settings
from app.ai.model_router import ModelRouter
from app.ai.story_verifier import verify_scene
from tests.ai.fakes import FakeAIClient


def _router(scripted):
    return ModelRouter(FakeAIClient(scripted),
                       Settings(openrouter_api_key="k",
                                verifier_models=["v1", "v2"], rpm_limit=1000))


def test_parses_accept_verdict():
    payload = json.dumps({"verdict": "accept",
                          "scores": {"coherence": 8, "voice": 7, "grounding": 9},
                          "issues": [], "fix_hints": []})
    v = verify_scene("scene", "ctx", _router([payload]), generator_model="d1", threshold=6)
    assert v.passed(6) is True


def test_cross_model_excludes_generator():
    payload = json.dumps({"verdict": "accept", "scores": {"coherence": 7}})
    fake = FakeAIClient([payload])
    router = ModelRouter(fake, Settings(openrouter_api_key="k",
                                        verifier_models=["v1", "v2"], rpm_limit=1000))
    verify_scene("scene", "ctx", router, generator_model="v1", threshold=6)
    assert fake.calls[0][0] == "v2"  # skipped the generator's model


def test_unparseable_is_reject():
    v = verify_scene("scene", "ctx", _router(["not json at all"]),
                     generator_model="d1", threshold=6)
    assert v.verdict == "reject"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_story_verifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.story_verifier'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/story_verifier.py`:
```python
from __future__ import annotations
import json
from app.ai.model_router import ModelRouter
from app.models.schemas import VerifierVerdict

_SYSTEM = (
    "You are a strict story editor. Judge the SCENE for coherence, character voice, "
    "tone/pacing, continuity, and grounding in the provided CONTEXT. "
    "Reply with ONLY a JSON object: "
    '{"verdict":"accept|revise|reject","scores":{"coherence":0-10,"voice":0-10,'
    '"grounding":0-10},"issues":[],"fix_hints":[]}'
)


def verify_scene(scene_text: str, packed_context: str, router: ModelRouter, *,
                 generator_model: str, threshold: int) -> VerifierVerdict:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"CONTEXT:\n{packed_context}\n\nSCENE:\n{scene_text}\n\n"
                                    f"Acceptance threshold per score: {threshold}."},
    ]
    result = router.complete("verifier", messages, json_mode=True, exclude_model=generator_model)
    try:
        data = json.loads(result.content)
        return VerifierVerdict(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return VerifierVerdict(verdict="reject", issues=["unparseable verifier output"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_story_verifier.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/story_verifier.py backend/tests/ai/test_story_verifier.py
git commit -m "feat(ai): cross-model LLM verifier with JSON verdict"
```

---

### Task 11: Story worker (draft / revise / summarize)

**Files:**
- Create: `backend/app/ai/story_worker.py`
- Test: `backend/tests/ai/test_story_worker.py`

**Interfaces:**
- Consumes: `ModelRouter` (Task 4), `StoryBeat` (Task 2).
- Produces:
  - `draft_scene(beat: StoryBeat, packed_context: str, router: ModelRouter) -> tuple[str, str]` — returns `(scene_text, model_used)` via worker tier.
  - `revise_scene(previous: str, fix_hints: list[str], packed_context: str, router: ModelRouter) -> tuple[str, str]`.
  - `summarize(text: str, router: ModelRouter) -> str` — worker-tier compression to ~2 sentences.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_story_worker.py`:
```python
from app.config import Settings
from app.ai.model_router import ModelRouter
from app.ai.story_worker import draft_scene, revise_scene, summarize
from app.models.schemas import StoryBeat
from tests.ai.fakes import FakeAIClient


def _router(scripted):
    return ModelRouter(FakeAIClient(scripted),
                       Settings(openrouter_api_key="k", worker_models=["w1"], rpm_limit=1000))


def test_draft_returns_text_and_model():
    beat = StoryBeat(id="b1", arc_id="a1", act=1, order=0, summary="farmer finds dead fish")
    text, model = draft_scene(beat, "CONTEXT", _router(["A tense scene by the lake."]))
    assert "lake" in text and model == "w1"


def test_revise_includes_hints():
    fake = FakeAIClient(["revised text"])
    router = ModelRouter(fake, Settings(openrouter_api_key="k", worker_models=["w1"], rpm_limit=1000))
    out, _ = revise_scene("old", ["make Mira hostile"], "CONTEXT", router)
    assert out == "revised text"
    assert "make Mira hostile" in fake.calls[0][1][-1]["content"]


def test_summarize():
    assert summarize("long text", _router(["short summary"])) == "short summary"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_story_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.story_worker'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/story_worker.py`:
```python
from __future__ import annotations
from app.ai.model_router import ModelRouter
from app.models.schemas import StoryBeat


def draft_scene(beat: StoryBeat, packed_context: str, router: ModelRouter) -> tuple[str, str]:
    messages = [
        {"role": "system", "content": "You are a game scene writer. Write vivid, grounded prose "
                                      "consistent with the CONTEXT. Do not invent locations or "
                                      "characters absent from CONTEXT."},
        {"role": "user", "content": f"CONTEXT:\n{packed_context}\n\nBEAT (act {beat.act}): "
                                    f"{beat.summary}\n\nWrite the scene."},
    ]
    res = router.complete("worker", messages, temperature=0.9)
    return res.content, res.model


def revise_scene(previous: str, fix_hints: list[str], packed_context: str,
                 router: ModelRouter) -> tuple[str, str]:
    hints = "; ".join(fix_hints)
    messages = [
        {"role": "system", "content": "Revise the SCENE to fix the listed problems while keeping "
                                      "what works. Stay grounded in CONTEXT."},
        {"role": "user", "content": f"CONTEXT:\n{packed_context}\n\nSCENE:\n{previous}\n\n"
                                    f"FIXES REQUIRED: {hints}"},
    ]
    res = router.complete("worker", messages, temperature=0.7)
    return res.content, res.model


def summarize(text: str, router: ModelRouter) -> str:
    messages = [
        {"role": "system", "content": "Summarize in at most two sentences, preserving named "
                                      "characters, locations, and revealed facts."},
        {"role": "user", "content": text},
    ]
    return router.complete("worker", messages, temperature=0.2).content
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_story_worker.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/story_worker.py backend/tests/ai/test_story_worker.py
git commit -m "feat(ai): story worker draft/revise/summarize"
```

---

### Task 12: Story director (orchestration + repair loop + persistence)

**Files:**
- Create: `backend/app/ai/story_director.py`
- Test: `backend/tests/ai/test_story_director.py`

**Interfaces:**
- Consumes: everything above (`ModelRouter`, `Retriever`, `StoryBible`, `validate_proposal`, `verify_scene`, worker funcs), schemas `StoryArc`/`StoryBeat`/`Scene`/`AIProposal`.
- Produces:
  - `generate_outline(world_id: str, conn, router: ModelRouter, retriever: Retriever) -> StoryArc` — director-tier JSON outline → persists `story_arcs` + `story_beats`.
  - `generate_story(world_id: str, conn, router: ModelRouter, retriever: Retriever, bible: StoryBible, *, max_repair: int, threshold: int) -> StoryArc` — for each beat: draft → validate → verify (cross-model) → repair loop (≤ `max_repair`) → on pass persist `Scene` (status `approved`) + summarize into bible; on fail persist `Scene` (status `needs_human_review`). Returns the arc.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_story_director.py`:
```python
import json
from app.config import Settings
from app.persistence.database import get_connection, init_db
from app.engine.world_generator import generate_world
from app.ai.model_router import ModelRouter
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible
from app.ai.rag.retriever import Retriever
from app.ai.story_director import generate_outline, generate_story
from tests.ai.fakes import FakeAIClient


def _world(db):
    init_db(db)
    conn = get_connection(db)
    data = generate_world(seed=11)
    wid = data["world"]["id"]
    for s in data["structures"]:
        conn.execute("INSERT INTO structures (id, world_id, type, layer) VALUES (?,?,?,?)",
                     (s["id"], s["world_id"], s["type"], s["layer"]))
    for n in data["npcs"]:
        conn.execute("INSERT INTO npcs (id, name, faction_id, location_id, role) VALUES (?,?,?,?,?)",
                     (n["id"], n["name"], n["faction_id"], n["location_id"], n["role"]))
    conn.commit()
    return conn, wid


_OUTLINE = json.dumps({
    "title": "The Mutated Lake", "premise": "Magic leaks into Moonlake", "theme": "decay",
    "beats": [
        {"act": 1, "summary": "Farmer finds dead fish",
         "location_ids": ["struct_moonlake"], "character_ids": ["npc_001"], "faction_ids": []},
    ],
})
_GOOD_VERDICT = json.dumps({"verdict": "accept",
                            "scores": {"coherence": 8, "voice": 7, "grounding": 8}})


def test_generate_outline_persists(tmp_path):
    conn, wid = _world(tmp_path / "o.db")
    try:
        router = ModelRouter(FakeAIClient([_OUTLINE]),
                             Settings(openrouter_api_key="k", director_models=["d1"], rpm_limit=1000))
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        arc = generate_outline(wid, conn, router, Retriever(conn, bible))
        assert arc.title == "The Mutated Lake"
        beats = conn.execute("SELECT * FROM story_beats WHERE arc_id = ?", (arc.id,)).fetchall()
        assert len(beats) == 1
    finally:
        conn.close()


def test_generate_story_happy_path(tmp_path):
    conn, wid = _world(tmp_path / "s.db")
    try:
        # outline (director) -> draft (worker) -> verdict (verifier) -> summary (worker)
        client = FakeAIClient([_OUTLINE, "A grim scene at Moonlake.", _GOOD_VERDICT, "Farmer sees dead fish."])
        router = ModelRouter(client, Settings(openrouter_api_key="k",
                                              director_models=["d1"], worker_models=["w1"],
                                              verifier_models=["v1"], rpm_limit=1000))
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        retriever = Retriever(conn, bible)
        arc = generate_story(wid, conn, router, retriever, bible, max_repair=2, threshold=6)
        scenes = conn.execute("SELECT * FROM scenes").fetchall()
        assert len(scenes) == 1 and scenes[0]["status"] == "approved"
        assert len(bible.all_entries(wid)) >= 1  # scene summarized into bible
    finally:
        conn.close()


def test_repair_loop_flags_for_review(tmp_path):
    conn, wid = _world(tmp_path / "r.db")
    try:
        bad = json.dumps({"verdict": "revise", "scores": {"coherence": 3}, "fix_hints": ["tighten"]})
        # outline, draft, verdict(bad), revise, verdict(bad), revise, verdict(bad) -> exhaust
        client = FakeAIClient([_OUTLINE, "draft", bad, "rev1", bad, "rev2", bad])
        router = ModelRouter(client, Settings(openrouter_api_key="k",
                                              director_models=["d1"], worker_models=["w1"],
                                              verifier_models=["v1"], rpm_limit=1000))
        bible = StoryBible(conn, HashEmbedder(64), VectorStore(conn, 64))
        arc = generate_story(wid, conn, router, Retriever(conn, bible), bible, max_repair=2, threshold=6)
        scenes = conn.execute("SELECT * FROM scenes").fetchall()
        assert scenes[0]["status"] == "needs_human_review"
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_story_director.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ai.story_director'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/ai/story_director.py`:
```python
from __future__ import annotations
import json
import sqlite3
import uuid
from app.ai.model_router import ModelRouter
from app.ai.rag.retriever import Retriever
from app.ai.rag.story_bible import StoryBible
from app.ai.ai_validator import validate_proposal
from app.ai.story_verifier import verify_scene
from app.ai.story_worker import draft_scene, revise_scene, summarize
from app.models.schemas import StoryArc, StoryBeat, Scene, AIProposal

_OUTLINE_SYSTEM = (
    "You are a game story director. Using the WORLD FACTS, design a grounded multi-act arc. "
    "Reply with ONLY JSON: "
    '{"title":"","premise":"","theme":"","beats":[{"act":1,"summary":"",'
    '"location_ids":[],"character_ids":[],"faction_ids":[]}]}. '
    "Only reference ids present in WORLD FACTS."
)


def generate_outline(world_id, conn: sqlite3.Connection, router: ModelRouter,
                     retriever: Retriever) -> StoryArc:
    facts = retriever.world_facts()
    messages = [
        {"role": "system", "content": _OUTLINE_SYSTEM},
        {"role": "user", "content": f"WORLD FACTS:\n{facts}\n\nDesign the arc."},
    ]
    data = json.loads(router.complete("director", messages, json_mode=True).content)
    arc_id = f"arc_{uuid.uuid4().hex[:8]}"
    beat_ids: list[str] = []
    for i, b in enumerate(data.get("beats", [])):
        beat = StoryBeat(id=f"beat_{uuid.uuid4().hex[:8]}", arc_id=arc_id,
                         act=int(b.get("act", 1)), order=i, summary=b.get("summary", ""),
                         location_ids=b.get("location_ids", []),
                         character_ids=b.get("character_ids", []),
                         faction_ids=b.get("faction_ids", []))
        beat_ids.append(beat.id)
        conn.execute(
            'INSERT INTO story_beats (id, arc_id, act, "order", summary, location_ids, '
            "character_ids, faction_ids, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (beat.id, beat.arc_id, beat.act, beat.order, beat.summary,
             json.dumps(beat.location_ids), json.dumps(beat.character_ids),
             json.dumps(beat.faction_ids), beat.status),
        )
    arc = StoryArc(id=arc_id, world_id=world_id, title=data.get("title", ""),
                   premise=data.get("premise", ""), theme=data.get("theme", ""), beats=beat_ids)
    conn.execute("INSERT INTO story_arcs (id, world_id, title, premise, theme, beats) VALUES (?,?,?,?,?,?)",
                 (arc.id, arc.world_id, arc.title, arc.premise, arc.theme, json.dumps(arc.beats)))
    conn.commit()
    return arc


def _load_beats(conn, arc_id) -> list[StoryBeat]:
    rows = conn.execute('SELECT * FROM story_beats WHERE arc_id = ? ORDER BY "order"', (arc_id,)).fetchall()
    return [StoryBeat(id=r["id"], arc_id=r["arc_id"], act=r["act"], order=r["order"],
                      summary=r["summary"], location_ids=json.loads(r["location_ids"]),
                      character_ids=json.loads(r["character_ids"]),
                      faction_ids=json.loads(r["faction_ids"]), status=r["status"]) for r in rows]


def _persist_scene(conn, scene: Scene) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO scenes (id, beat_id, title, prose, dialogue, "
        "storyboard_card_id, revealed_information, status) VALUES (?,?,?,?,?,?,?,?)",
        (scene.id, scene.beat_id, scene.title, scene.prose, json.dumps(scene.dialogue),
         scene.storyboard_card_id, json.dumps(scene.revealed_information), scene.status),
    )
    conn.commit()


def generate_story(world_id, conn: sqlite3.Connection, router: ModelRouter,
                   retriever: Retriever, bible: StoryBible, *, max_repair: int,
                   threshold: int) -> StoryArc:
    arc = generate_outline(world_id, conn, router, retriever)
    for beat in _load_beats(conn, arc.id):
        ctx = retriever.retrieve(beat.summary, k=5, location_ids=beat.location_ids or None,
                                 character_ids=beat.character_ids or None,
                                 faction_ids=beat.faction_ids or None)
        packed = ctx.pack(char_budget=6000)

        proposal = AIProposal(id=f"prop_{uuid.uuid4().hex[:8]}", proposal_type="scene",
                              referenced_world_ids=beat.location_ids + beat.character_ids,
                              payload={"location_id": beat.location_ids[0] if beat.location_ids else None,
                                       "character_ids": beat.character_ids})
        scene = Scene(id=f"scene_{uuid.uuid4().hex[:8]}", beat_id=beat.id,
                      title=beat.summary[:60], revealed_information=[])

        reasons = validate_proposal(proposal, conn)
        if reasons:
            scene.status = "rejected"
            scene.prose = "; ".join(reasons)
            _persist_scene(conn, scene)
            continue

        text, gen_model = draft_scene(beat, packed, router)
        approved = False
        for _ in range(max_repair + 1):
            verdict = verify_scene(text, packed, router, generator_model=gen_model, threshold=threshold)
            if verdict.passed(threshold):
                approved = True
                break
            if verdict.verdict == "reject" or not verdict.fix_hints:
                break
            text, gen_model = revise_scene(text, verdict.fix_hints, packed, router)

        scene.prose = text
        scene.status = "approved" if approved else "needs_human_review"
        _persist_scene(conn, scene)
        if approved:
            bible.add_entry(world_id, "scene", scene.id, summarize(text, router))
    return arc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/ai/test_story_director.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/ai/story_director.py backend/tests/ai/test_story_director.py
git commit -m "feat(ai): story director orchestration with repair loop + bible persistence"
```

---

### Task 13: API routes + wiring + run docs

**Files:**
- Create: `backend/app/api/routes_ai.py`
- Modify: `backend/app/main.py`
- Modify: `backend/README.md`
- Test: `backend/tests/ai/test_routes_ai.py`

**Interfaces:**
- Consumes: all of the above; FastAPI dependency `get_router() -> ModelRouter` (overridable in tests via `app.dependency_overrides`).
- Produces endpoints:
  - `POST /api/ai/story/generate?world_id=...` → builds router/retriever/bible, calls `generate_story`, returns `{arc, scene_count}`.
  - `GET /api/ai/story/{world_id}` → returns arcs + beats + scenes.
  - `POST /api/ai/proposal/validate` (body: `AIProposal`) → returns `{valid, reasons}`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ai/test_routes_ai.py`:
```python
import json
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes_ai import get_router
from app.config import Settings
from app.ai.model_router import ModelRouter
from tests.ai.fakes import FakeAIClient

_OUTLINE = json.dumps({"title": "T", "premise": "p", "theme": "decay",
                       "beats": [{"act": 1, "summary": "dead fish at lake",
                                  "location_ids": ["struct_moonlake"],
                                  "character_ids": ["npc_001"], "faction_ids": []}]})
_VERDICT = json.dumps({"verdict": "accept", "scores": {"coherence": 8, "voice": 7, "grounding": 8}})


def test_generate_and_fetch_story():
    client = TestClient(app)
    world = client.post("/api/world/new", params={"seed": 99}).json()
    wid = world["world"]["id"]

    def fake_router():
        c = FakeAIClient([_OUTLINE, "scene prose at the lake", _VERDICT, "summary"])
        return ModelRouter(c, Settings(openrouter_api_key="k", director_models=["d1"],
                                       worker_models=["w1"], verifier_models=["v1"], rpm_limit=1000))

    app.dependency_overrides[get_router] = fake_router
    try:
        gen = client.post("/api/ai/story/generate", params={"world_id": wid}).json()
        assert gen["scene_count"] == 1
        story = client.get(f"/api/ai/story/{wid}").json()
        assert len(story["arcs"]) == 1 and len(story["scenes"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_validate_endpoint_rejects_bad_location():
    client = TestClient(app)
    client.post("/api/world/new", params={"seed": 1})
    body = {"id": "p1", "proposal_type": "scene", "payload": {"location_id": "struct_nowhere"}}
    resp = client.post("/api/ai/proposal/validate", json=body).json()
    assert resp["valid"] is False and resp["reasons"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/ai/test_routes_ai.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.routes_ai'`.

- [ ] **Step 3: Write implementation**

Create `backend/app/api/routes_ai.py`:
```python
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from app.config import get_settings
from app.ai.ai_client import OpenRouterClient
from app.ai.model_router import ModelRouter
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible
from app.ai.rag.retriever import Retriever
from app.ai.story_director import generate_story
from app.ai.ai_validator import validate_proposal
from app.persistence.database import get_connection, init_db
from app.models.schemas import AIProposal

router = APIRouter(prefix="/api/ai")


def get_router() -> ModelRouter:
    s = get_settings()
    client = OpenRouterClient(s.openrouter_api_key, s.openrouter_base_url, s.request_timeout)
    return ModelRouter(client, s)


@router.post("/story/generate")
def generate(world_id: str, model_router: ModelRouter = Depends(get_router)):
    init_db()
    s = get_settings()
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM worlds WHERE id = ?", (world_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="World not found")
        embedder = HashEmbedder(dim=s.embedding_dim)
        bible = StoryBible(conn, embedder, VectorStore(conn, embedder.dim))
        retriever = Retriever(conn, bible)
        arc = generate_story(world_id, conn, model_router, retriever, bible,
                             max_repair=s.max_repair_attempts, threshold=s.verifier_threshold)
        scene_count = conn.execute(
            "SELECT COUNT(*) AS c FROM scenes s JOIN story_beats b ON s.beat_id = b.id "
            "WHERE b.arc_id = ?", (arc.id,)).fetchone()["c"]
        return {"arc": arc.model_dump(mode="json"), "scene_count": scene_count}
    finally:
        conn.close()


@router.get("/story/{world_id}")
def get_story(world_id: str):
    conn = get_connection()
    try:
        arcs = [dict(r) for r in conn.execute("SELECT * FROM story_arcs WHERE world_id = ?", (world_id,)).fetchall()]
        arc_ids = [a["id"] for a in arcs]
        beats, scenes = [], []
        if arc_ids:
            marks = ",".join("?" for _ in arc_ids)
            beats = [dict(r) for r in conn.execute(
                f'SELECT * FROM story_beats WHERE arc_id IN ({marks}) ORDER BY "order"', arc_ids).fetchall()]
            beat_ids = [b["id"] for b in beats]
            if beat_ids:
                bmarks = ",".join("?" for _ in beat_ids)
                scenes = [dict(r) for r in conn.execute(
                    f"SELECT * FROM scenes WHERE beat_id IN ({bmarks})", beat_ids).fetchall()]
        return {"arcs": arcs, "beats": beats, "scenes": scenes}
    finally:
        conn.close()


@router.post("/proposal/validate")
def validate(proposal: AIProposal):
    conn = get_connection()
    try:
        reasons = validate_proposal(proposal, conn)
        return {"valid": len(reasons) == 0, "reasons": reasons}
    finally:
        conn.close()
```

Modify `backend/app/main.py` — add import and registration:
```python
from app.api.routes_ai import router as ai_router
```
and after `app.include_router(world_router)`:
```python
app.include_router(ai_router)
```

Append to `backend/README.md`:
```markdown

## AI Story Layer (Stage 1)

Set `OPENROUTER_API_KEY` (see `.env.example`). Endpoints:
- `POST /api/ai/story/generate?world_id=...` — generate a verified, grounded story.
- `GET /api/ai/story/{world_id}` — fetch arcs/beats/scenes.
- `POST /api/ai/proposal/validate` — deterministic proposal check.

Tests run fully offline (FakeAIClient + HashEmbedder): `python -m pytest`.
```

- [ ] **Step 4: Run the full suite & commit**

Run: `cd backend && python -m pytest -v` → Expected: PASS (all tasks, no network).
```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/app/api/routes_ai.py backend/app/main.py backend/README.md backend/tests/ai/test_routes_ai.py
git commit -m "feat(ai): story generation + validation API endpoints"
```

---

### Task 14 (optional): Live smoke test

**Files:**
- Test: `backend/tests/ai/test_live_smoke.py`

**Interfaces:** Consumes real `OpenRouterClient` + `get_settings()`; skipped unless `RUN_LIVE_AI=1`.

- [ ] **Step 1: Write the gated test**

Create `backend/tests/ai/test_live_smoke.py`:
```python
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
```

- [ ] **Step 2: Run it (only when you have a key)**

Run: `cd backend && RUN_LIVE_AI=1 python -m pytest tests/ai/test_live_smoke.py -v`
Expected: PASS (or SKIP when `RUN_LIVE_AI` unset).

- [ ] **Step 3: Commit**

```bash
cd "C:/Users/NPC/Desktop/Aetherfall"
git add backend/tests/ai/test_live_smoke.py
git commit -m "test(ai): optional gated live smoke test"
```

---

## Self-Review

**Spec coverage:**
- Hierarchical generation / deep-story-beyond-context → Tasks 8 (packer/budget), 11 (summarize), 12 (orchestration). ✓
- RAG over story bible + world state → Tasks 5–8. ✓
- Tiered free routing (director/worker + summarize) → Tasks 1, 4, 11. ✓
- Local embeddings + same-DB vector store → Tasks 5, 6 (NumPy brute-force; sqlite-vec noted as upgrade). ✓
- Two-layer verification, cross-model → Task 9 (deterministic) + Task 10 (cross-model LLM) + Task 12 (repair loop). ✓
- Safety/secrets, JSON proposals, no direct canonical mutation → Tasks 1 (`.env`), 9 (forbidden keys), 12 (approval path). ✓
- Offline deterministic tests → every task uses `FakeAIClient` + `HashEmbedder`. ✓
- Storyboard cards → `StoryboardCard` schema exists; `Scene.storyboard_card_id` reserved. **Gap:** a dedicated `storyboard_planner.py` (spec §4) is not yet a task. **Resolution:** deferred as a thin follow-up — Stage 1's verified scenes are the prerequisite; add it as Task 15 if storyboard cards are needed before Stage 2 (it reuses the worker tier + validator with `proposal_type="storyboard"`).

**Placeholder scan:** none — every code/test step contains complete code.

**Type consistency:** `RouterResult.content/model`, `Embedder.embed/dim`, `VectorStore.add/query`, `StoryBible.add_entry/search/all_entries`, `RetrievedContext.pack`, `validate_proposal -> list[str]`, `verify_scene -> VerifierVerdict`, `VerifierVerdict.passed`, worker `(text, model)` tuples, and `generate_story(... max_repair, threshold)` are used identically across Tasks 4–13. ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-23-stage1-story-rag.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
