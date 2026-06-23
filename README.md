# Aetherworld Coding Agent Pack

This folder is a linked documentation pack for a text-only coding agent such as opencode.

The product is a web-based 2D/2.5D systemic open-world RPG. The frontend runs in the browser, but the important world logic lives in Python. AI can suggest content, but deterministic Python systems must validate every suggestion before it becomes part of the saved world.

## Read Order

1. [Product Spec](./PRODUCT_SPEC.md)
2. [Python Web Architecture](./PYTHON_WEB_ARCHITECTURE.md)
3. [World Generation](./WORLD_GENERATION.md)
4. [AI Story and Validation](./AI_STORY_VALIDATION.md)
5. [Data Schemas](./DATA_SCHEMAS.md)
6. [Implementation Roadmap](./IMPLEMENTATION_ROADMAP.md)
7. [Evaluation Checklist](./EVALUATION_CHECKLIST.md)
8. [Opencode Prompt](./OPENCODE_PROMPT.md)

## Core Rule

Noise creates natural possibility. Rules decide final placement. Storyboard gives cinematic meaning. Validation protects the game from AI chaos.

## MVP Target

Build one playable region first: Riverfall Valley.

It should contain:

- one town
- farms around the town
- one river
- one lake
- one forest
- one old castle or fort
- one cave entrance
- one underground dungeon
- one small floating island
- three factions
- twenty NPCs
- basic six-principle power system
- AI storyboard proposals
- deterministic validation and repair pipeline

Do not start with full infinite world, multiplayer, full ocean simulation, or real-time image generation.

