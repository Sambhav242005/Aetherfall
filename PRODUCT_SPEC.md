# Product Spec

See also:

- [Python Web Architecture](./PYTHON_WEB_ARCHITECTURE.md)
- [World Generation](./WORLD_GENERATION.md)
- [AI Story and Validation](./AI_STORY_VALIDATION.md)
- [Evaluation Checklist](./EVALUATION_CHECKLIST.md)

## Product Identity

Aetherworld is a web-based 2D/2.5D systemic open-world RPG where the world, characters, factions, powers, structures, quests, and story events are generated from six universal power principles.

The game is not an unrestricted AI sandbox. It must use deterministic rules, persistent world state, and validated AI suggestions.

## Six Power Principles

Every character, structure, faction, dungeon, weapon, and story conflict can be influenced by one or more of these principles:

| Principle | World Expression |
|---|---|
| Magic | floating islands, elemental temples, mana lakes |
| Aura | warrior clans, training arenas, monks, body power |
| Alchemy | labs, mutation zones, crystal ruins, potion gardens |
| Mechanical | factories, clockwork cities, machine dungeons |
| Biological/Primal | living forests, beast nests, root castles, evolution |
| Mind/Psychic | dream palaces, illusion mazes, memory temples |

All powers must share one internal schema. Do not create six unrelated ability systems.

## World Layers

The world uses layers, not only X/Y map position.

```text
Location = x + y + layer
```

Required layers:

| Layer | Content |
|---|---|
| Sky | floating islands, sky shrines, airship docks |
| Surface | towns, farms, rivers, forests, castles |
| Underground | caves, mines, dungeons, hidden tunnels |
| Deep | ancient ruins, abyss zones, magma zones |
| Ocean | ports, islands, sea ruins, underwater dungeons |

MVP should include Sky, Surface, and Underground. Deep and Ocean can come later.

## MVP Region

MVP region name: Riverfall Valley.

Surface:

- Riverfall Town
- farms
- Moonlake
- Northwood Forest
- Old Stone Castle
- broken bridge

Underground:

- cave connected from surface
- abandoned alchemy dungeon below the castle
- crystal cave below Moonlake

Sky:

- small floating island above Moonlake
- ancient magic shrine

Main conflict:

The floating island leaks magic into the lake. The lake mutates crops. Farmers become sick. The castle lord hides an old alchemy experiment. The alchemy guild wants to harvest crystals from the lake.

## Non-Negotiable Rules

- AI must not directly mutate canonical game state.
- Every AI output is an untrusted proposal.
- Every underground structure needs a valid entrance unless intentionally sealed for story.
- Large structures must reserve space before small objects are placed.
- Visual overlap is allowed. Gameplay overlap must be validated.
- The world can use grid/chunks internally, but the visible world must look natural and not block-based.
- Save state must separate seed-generated base world from player changes.

