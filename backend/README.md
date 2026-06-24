# Aetherworld Backend

FastAPI-based backend for the Aetherworld RPG engine.

## AI Story Layer (Stage 1)

Set `OPENROUTER_API_KEY` (see `.env.example`). Endpoints:
- `POST /api/ai/story/generate?world_id=...` — generate a verified, grounded story.
- `GET /api/ai/story/{world_id}` — fetch arcs/beats/scenes.
- `POST /api/ai/proposal/validate` — deterministic proposal check.

Tests run fully offline (FakeAIClient + HashEmbedder): `python -m pytest`.
