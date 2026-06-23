# Implementation Roadmap

See also:

- [Product Spec](./PRODUCT_SPEC.md)
- [Python Web Architecture](./PYTHON_WEB_ARCHITECTURE.md)
- [Evaluation Checklist](./EVALUATION_CHECKLIST.md)

## Phase 1: Project Skeleton

Build:

- FastAPI app
- static browser client
- health endpoint
- world creation endpoint
- SQLite connection
- Pydantic schema module

Do not add AI yet.

## Phase 2: Seeded MVP World

Build:

- seed-based region generator
- chunk model
- basic height/moisture/heat maps
- simple biome assignment
- surface layer only
- JSON snapshot endpoint

Acceptance:

- same seed generates same base world
- chunk endpoint returns stable data

## Phase 3: Natural Map Renderer

Build:

- browser canvas renderer
- chunk loading
- terrain colors/masks
- river and road curves
- structure markers

Acceptance:

- world does not look like raw square blocks
- player can pan around region

## Phase 4: Structures and Overlap Validation

Build:

- structure blueprint model
- footprint and reservation system
- influence zone and exclusion zone
- overlap validator
- repair pass

Acceptance:

- no farm inside lake
- no cave blocked by house
- road crossing river gets bridge or reroute

## Phase 5: Layers and Entrances

Build:

- Sky, Surface, Underground layers
- entrance contract model
- cave mouth to underground transition
- return exit

Acceptance:

- cave entrance on surface loads underground chunk
- underground dungeon has return exit

## Phase 6: Factions, NPCs, and Power Identity

Build:

- faction model
- NPC model
- six-principle power profile
- region conflict seed data

Acceptance:

- Riverfall Valley has three factions and twenty NPCs
- each important place has power influence and owner/purpose

## Phase 7: AI Proposal System

Build:

- AI proposal schema
- mock AI proposal endpoint first
- storyboard card validator
- world fact checker

Acceptance:

- invalid proposal is rejected with reasons
- approved proposal does not mutate state until validation passes

## Phase 8: Local AI Integration

Build:

- Ollama client
- JSON-only prompt wrapper
- retry limit
- proposal logging

Acceptance:

- AI can propose dialogue/storyboard cards
- malformed output does not crash engine
- AI cannot bypass validation

