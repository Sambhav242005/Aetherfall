# Evaluation Checklist

See also:

- [Product Spec](./PRODUCT_SPEC.md)
- [Python Web Architecture](./PYTHON_WEB_ARCHITECTURE.md)
- [World Generation](./WORLD_GENERATION.md)
- [AI Story and Validation](./AI_STORY_VALIDATION.md)

Use this checklist after every coding pass.

## Product Scope

- [ ] MVP remains one region only.
- [ ] No multiplayer added.
- [ ] No full ocean simulation added.
- [ ] No real-time image generation added.
- [ ] No unrelated systems added.

## Python Authority

- [ ] Python backend owns canonical state.
- [ ] Browser does not directly mutate world state.
- [ ] Pydantic validates API inputs.
- [ ] Game actions go through deterministic engine functions.

## World Generation

- [ ] Same seed creates same base world.
- [ ] World data is chunked.
- [ ] Visible map avoids block-like design.
- [ ] Rivers, roads, forests, and biomes use organic shapes.
- [ ] Major structures reserve space before small decorations.

## Structures

- [ ] Every major structure has footprint, influence zone, and exclusion zone.
- [ ] Caves and dungeons have entrance contracts.
- [ ] Underground playable areas have return exits.
- [ ] Repair pass handles common conflicts.

## AI Safety

- [ ] AI output is treated as proposal only.
- [ ] AI cannot directly edit inventory, combat, quest completion, ownership, or map geometry.
- [ ] AI output uses structured JSON for engine operations.
- [ ] Invalid AI output is rejected with reasons.
- [ ] Storyboard proposals are validated against existing world facts.

## Save System

- [ ] Base world and player changes are separated.
- [ ] Runtime state is not confused with canonical save state.
- [ ] Reloading does not move generated structures.

## Tests

- [ ] Unit tests exist for validators.
- [ ] Same seed test exists.
- [ ] Overlap rejection test exists.
- [ ] Entrance contract test exists.
- [ ] AI invalid proposal test exists.

