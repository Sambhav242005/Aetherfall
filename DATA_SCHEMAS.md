# Data Schemas

See also:

- [Python Web Architecture](./PYTHON_WEB_ARCHITECTURE.md)
- [World Generation](./WORLD_GENERATION.md)
- [AI Story and Validation](./AI_STORY_VALIDATION.md)

These are conceptual schemas for the coding agent. Implement them as Pydantic models first.

## World

```python
class World:
    id: str
    seed: int
    name: str
    base_generated_version: str
    current_tick: int
    regions: list[str]
```

## Chunk

```python
class Chunk:
    id: str
    world_id: str
    layer: str
    chunk_x: int
    chunk_y: int
    biome: str
    terrain_cells: list[dict]
    structures: list[str]
    entities: list[str]
    danger_level: float
    power_influence: dict[str, float]
```

## Structure

```python
class Structure:
    id: str
    world_id: str
    type: str
    layer: str
    position: dict
    footprint: dict
    influence_zone: dict
    exclusion_zone: dict
    entrances: list[str]
    owner_faction_id: str | None
    power_influence: dict[str, float]
    story_hooks: list[str]
```

## Entrance Contract

```python
class EntranceContract:
    id: str
    source_layer: str
    source_position: dict
    target_layer: str
    target_position: dict
    access_type: str
    is_returnable: bool
    locked_by: str | None
```

## Faction

```python
class Faction:
    id: str
    name: str
    principle_bias: list[str]
    home_structure_id: str | None
    goals: list[str]
    relationships: dict[str, int]
```

## NPC

```python
class NPC:
    id: str
    name: str
    faction_id: str | None
    location_id: str
    role: str
    personality_tags: list[str]
    known_facts: list[str]
    secrets: list[str]
    power_profile: dict
    alive: bool
```

## AI Proposal

```python
class AIProposal:
    id: str
    proposal_type: str
    source: str
    referenced_world_ids: list[str]
    payload: dict
    validation_status: str
    rejection_reasons: list[str]
```

## Storyboard Card

```python
class StoryboardCard:
    id: str
    scene_title: str
    location_id: str
    characters_present: list[str]
    visual_focus: str
    mood: str
    gameplay_objective: str
    revealed_information: list[str]
    validation_requirements: list[str]
```

## Save Model

Separate three kinds of state:

```text
BaseWorld = seed-generated world
WorldDelta = player changes and approved canonical changes
RuntimeState = temporary simulation data
```

Do not regenerate the whole world after player changes. Regenerate missing chunks only when safe, then apply deltas.

