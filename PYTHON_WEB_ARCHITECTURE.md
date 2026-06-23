# Python Web Architecture

See also:

- [Product Spec](./PRODUCT_SPEC.md)
- [Data Schemas](./DATA_SCHEMAS.md)
- [Implementation Roadmap](./IMPLEMENTATION_ROADMAP.md)

## Recommended Stack

Use Python for the authoritative game engine.

| Layer | Choice |
|---|---|
| Backend API | FastAPI |
| Realtime updates | WebSocket endpoint in FastAPI |
| Persistence | SQLite for MVP, PostgreSQL later |
| Validation | Pydantic models |
| Game state | JSON snapshots plus database records |
| Local AI | Ollama-compatible local model, optional |
| Frontend | Browser app with Canvas, Phaser, PixiJS, or plain HTML canvas |
| Frontend build | Vite or simple static app for MVP |

FastAPI is preferred over Flask for this project because the game needs typed request/response models, WebSockets, and clean schema validation.

## Authority Rule

Python is authoritative.

The browser can:

- render map chunks
- show UI
- send player input
- request nearby world state
- display AI dialogue after approval

The browser cannot:

- decide combat results
- create structures
- approve AI output
- mutate inventory directly
- decide quest completion directly
- rewrite canonical world state

## High-Level Architecture

```text
Browser Client
  -> FastAPI API
  -> Python Game Engine
  -> Validators and Repair Passes
  -> SQLite State Store
  -> Approved World Snapshot
  -> Browser Renderer
```

## Suggested Backend Modules

```text
app/
  main.py
  api/
    routes_world.py
    routes_player.py
    routes_ai.py
    websocket.py
  engine/
    world_generator.py
    chunk_manager.py
    structure_placer.py
    overlap_validator.py
    repair_pass.py
    pathfinding.py
    simulation.py
  ai/
    story_director.py
    storyboard_planner.py
    ai_client.py
    ai_validator.py
  models/
    schemas.py
    enums.py
  persistence/
    database.py
    repositories.py
  tests/
```

## Suggested Frontend Modules

```text
web/
  index.html
  src/
    main.ts
    api.ts
    renderer/
      canvasRenderer.ts
      chunkRenderer.ts
      entityRenderer.ts
    ui/
      inspector.ts
      dialoguePanel.ts
```

The frontend can be TypeScript or JavaScript. Keep the logic thin.

## Core API Endpoints

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/world/new` | create a seeded MVP world |
| GET | `/api/world/{world_id}/chunk/{layer}/{x}/{y}` | load a chunk |
| GET | `/api/world/{world_id}/snapshot` | get current world summary |
| POST | `/api/player/action` | submit player action |
| POST | `/api/ai/storyboard/propose` | generate storyboard proposal |
| POST | `/api/ai/storyboard/validate` | validate proposal |
| WS | `/ws/world/{world_id}` | send world updates |

## Development Principle

Build the deterministic engine first. Add AI only after world generation, validation, saving, and loading work.

