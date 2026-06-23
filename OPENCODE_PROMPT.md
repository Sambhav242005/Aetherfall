# Prompt for Opencode or Another Text-Only Coding Agent

Copy this prompt and give it to the coding agent.

```text
You are working on Aetherworld, a web-based 2D/2.5D systemic open-world RPG.

Read these files first, in this order:

1. README.md
2. PRODUCT_SPEC.md
3. PYTHON_WEB_ARCHITECTURE.md
4. WORLD_GENERATION.md
5. AI_STORY_VALIDATION.md
6. DATA_SCHEMAS.md
7. IMPLEMENTATION_ROADMAP.md
8. EVALUATION_CHECKLIST.md

Your job:
Evaluate the project plan and then implement the next smallest useful MVP step.

The build must be web-based with Python as the authoritative backend.

Use this architecture:
- FastAPI backend
- Pydantic validation
- SQLite for MVP persistence
- deterministic Python game engine
- browser frontend for rendering and input
- optional Ollama/local AI later, but do not add AI until deterministic generation and validation work

Critical rules:
- AI must never directly mutate canonical game state.
- The browser must never directly mutate canonical game state.
- Every AI output is an untrusted proposal.
- Every generated cave/dungeon needs a valid entrance contract unless marked sealed.
- Large structures need footprint, influence zone, and exclusion zone.
- Visual overlap is allowed, but gameplay overlap must be validated.
- The world may use chunks internally, but the visible map must not look block-based.
- MVP must stay one region: Riverfall Valley.

First task:
Create a minimal FastAPI project that can:

1. create a seeded world called Riverfall Valley
2. generate a stable surface chunk from a seed
3. return chunk data as JSON
4. include Pydantic schemas for World, Chunk, Structure, EntranceContract, Faction, NPC, AIProposal, and StoryboardCard
5. include a basic validator that rejects a structure if it overlaps an incompatible reserved zone
6. include tests for deterministic seed generation and overlap rejection

Do not implement full AI yet.
Do not add multiplayer.
Do not add a giant open world.
Do not add real-time image generation.
Do not ignore the checklist.

Before editing code:
Briefly summarize what you understood from the docs.

After editing code:
Run tests if possible, then provide:
- files changed
- what works
- what is still missing
- risks
- next recommended task
```

