# Stage 1 Design — Aetherworld Story Director + RAG + Verification

**Date:** 2026-06-23
**Status:** Approved (brainstorming complete)
**Scope:** Stage 1 only — AI story generation, RAG memory, storyboard, and two-layer verification. Stage 2 (story-controlled noise maps) is explicitly **out of scope**.

---

## 1. Problem

Generate a **deep, multi-act story** for the existing Riverfall Valley world that is far longer than any single model's context window, while remaining:

- **Consistent** — no internal contradictions across a story longer than context.
- **Grounded** — every story fact references real world entities (structures, NPCs, factions) already in the DB.
- **Safe** — AI never mutates canonical state; every output is an untrusted proposal.

The "deeper than context" problem is solved by **hierarchical generation + summarization memory + retrieval (RAG)**: every LLM call sees only a compressed, retrieved slice — never the whole story.

## 2. Locked Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Stage 1 only (story + RAG + storyboard + verification). Map deferred. |
| RAG corpus | **Story Bible** (grows as story deepens) **+ canonical world state** (from SQLite), unified retrieval. |
| Model routing | **Tiered free**: strong Director, fast Workers, summarize-with-worker to compress context. |
| Embeddings / store | **Local embeddings** (BGE/nomic, lazy-loaded) + same-DB vector store. |
| Verification | **Two layers**: deterministic Validator + LLM Verifier. Verifier uses **cross-model** (different model than Director). |

### Surfaced deviation
The vector store is implemented as a same-DB table with **NumPy brute-force cosine** rather than the `sqlite-vec` native extension, because the extension is fragile to load on Windows and brute-force is correct and fast at MVP scale (hundreds of chunks). Interface is identical; `sqlite-vec` is a drop-in upgrade later.

## 3. Context: existing code

Additive AI layer on top of a working deterministic backend. Nothing existing is rewritten.

- `world_generator.py` — **hand-authored** Riverfall Valley (3 factions, 20 NPCs, ~11 structures). This is the ground truth the story must reference.
- `models/schemas.py` — `StoryboardCard` and `AIProposal` already exist; story schemas are added.
- `persistence/database.py` — `ai_proposals` + `storyboard_cards` tables already exist; story/bible/vector tables are added.
- `api/` — `routes_world.py` registered via `app.include_router` in `main.py`.
- Tests — pytest, `conftest.py` auto-resets the DB at `DB_PATH`. `httpx` available for `TestClient`.

## 4. Module layout (new)

```
backend/app/
  config.py                # NEW: pydantic-settings; API key, model tiers, thresholds, RPM
  ai/                      # NEW
    __init__.py
    ai_client.py           # OpenRouter HTTP client (httpx); JSON mode; ChatClient Protocol
    model_router.py        # tier -> ordered fallback model list; RPM limiter; fallback on failure
    story_director.py      # orchestration: outline -> fan-out -> validate -> verify -> repair -> bible
    story_worker.py        # draft_scene + summarize (FAST tier)
    storyboard_planner.py  # emit StoryboardCard from a scene
    ai_validator.py        # deterministic hard gate (no LLM)
    story_verifier.py      # LLM judge, CROSS-MODEL (VERIFIER tier != DIRECTOR tier)
    rag/
      __init__.py
      embeddings.py        # Embedder Protocol; HashEmbedder (deterministic) + LocalEmbedder (lazy)
      vector_store.py      # same-DB table + NumPy brute-force cosine
      story_bible.py       # bible records (text + embedding) write/read
      retriever.py         # hybrid retrieve (vector + SQL world facts) + token-budget packer
  api/routes_ai.py         # NEW: generate / status / validate
  models/schemas.py        # ADD: StoryArc, StoryBeat, Scene, BibleEntry, VerifierVerdict
```

## 5. Generation pipeline

```
1. Intake     read region facts from SQLite (structures, 3 factions, 20 NPCs, conflict)
2. Outline    Director (strong)  -> StoryArc with Acts -> StoryBeats, grounded in the lake-mutation conflict
3. Fan-out    for each Beat: Worker (fast) drafts a Scene (prose + dialogue) using retrieved context
4. Validate   deterministic ai_validator: references exist? contradiction? state-mutation attempt? -> reasons
5. Verify     CROSS-MODEL story_verifier (different model): coherence/voice/grounding scores -> accept|revise|reject
6. Repair     on "revise": Worker revises with fix_hints; loop max 2; then flag for human review
7. Compress   Worker summarizes the accepted Scene -> BibleEntry (text + embedding) -> vector store
8. Persist    approved Scene/Beat/Arc as canonical story records (Base vs Delta, mirroring BaseWorld/WorldDelta)
```

Every LLM prompt = `system role` + `retrieved bible slice` + `retrieved world facts` + `task`. Context stays bounded regardless of story length.

## 6. RAG design

- **Two sources, one retriever.** Story Bible (arcs/beats/scenes/character-notes the system writes) + canonical world state (read from existing tables).
- **Local embeddings.** `Embedder` Protocol. `HashEmbedder` is deterministic (used in all tests; no network, no torch). `LocalEmbedder` lazy-imports `sentence-transformers` only when actually used in production.
- **Vector store.** Same-DB `bible_vectors` table storing the embedding as JSON; `query()` does NumPy cosine over candidates and returns top-k.
- **Hybrid retrieval.** Semantic (vector) over the bible **plus** structured SQL filters over world state (by `location_id`, character, faction). Combined, then packed to a token budget; overflow is map-reduce summarized by a Worker before insertion.

## 7. Tiered model routing

Tiers are **ordered fallback lists** (free model IDs shift month-to-month, so config-driven):

| Tier | Default first choice | Role |
|---|---|---|
| `DIRECTOR` | `deepseek/deepseek-v3:free` (then `qwen/qwen3-235b-a22b:free`) | outline, coherence merge |
| `WORKER` | `meta-llama/llama-4-scout:free` (then `google/gemma-3-27b:free`) | bulk scene drafting + summarization |
| `VERIFIER` | `qwen/qwen3-235b-a22b:free` (then `deepseek/deepseek-r1:free`) | cross-model judge — **must differ from the model that produced the text** |

- **RPM limiter**: hard cap (default 20 req/min) with backoff; Workers do the high-volume calls, Director/Verifier are sparing.
- **Fallback**: on HTTP error / empty / rate-limit, advance to next model in the tier list.
- **Cross-model guarantee**: the router exposes the model id used to generate; the verifier call asserts a different id (and falls to the next verifier model if they collide).

## 8. Verification (two layers)

**Layer 1 — Validator (`ai_validator.py`, deterministic, no LLM):** hard gate.
- Valid JSON / proper `AIProposal`.
- Every referenced `location_id` / character / faction **exists** in DB.
- No contradiction with already-**approved** canonical events.
- No attempt to mutate canonical state (inventory, death, ownership, geometry, quest completion).
- Fail → instant reject with `rejection_reasons`.

**Layer 2 — Verifier (`story_verifier.py`, LLM judge, cross-model):** soft gate.
- Plot coherence, character voice/consistency, tone/pacing, continuity, grounding-in-retrieved-context.
- Returns `VerifierVerdict { verdict, scores, issues, fix_hints }`.
- Accept if `verdict == "accept"` and all scores ≥ threshold (default 6, from `EVALUATION_CHECKLIST.md`).
- Drives the bounded generator↔verifier repair loop (max 2 retries) before human-review flag.

## 9. Safety / secrets

- `OPENROUTER_API_KEY` via env / `.env` + `pydantic-settings`. Never hardcoded, never logged. (Rotate the key if it was ever pasted anywhere.)
- All engine-affecting AI output is strict JSON `AIProposal`; free-form text only for display dialogue.
- AI cannot write canonical state directly — only the validated approval path persists records.

## 10. Testing strategy

- **Offline & deterministic by default.** `FakeAIClient` (canned responses) + `HashEmbedder` mean the whole pipeline (router, retriever, validator, verifier, director, routes) is tested with **no network**.
- Validator: rejects bad reference / contradiction / mutation; accepts good proposal.
- Retriever: returns grounded world facts; packer respects token budget.
- Verifier: parses verdict; enforces cross-model (asserts different model id).
- Director: full pipeline end-to-end with fakes; repair loop terminates at cap.
- One **optional live smoke test** gated behind `RUN_LIVE_AI=1` hitting a real free model.

## 11. Out of scope (Stage 2)

Story-controlled noise maps, real noise generation in `world_generator.py`, the browser renderer. To be designed in a follow-up once Stage 1 produces a validated story + storyboard.
