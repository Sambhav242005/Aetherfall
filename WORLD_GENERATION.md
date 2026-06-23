# World Generation

See also:

- [Product Spec](./PRODUCT_SPEC.md)
- [Data Schemas](./DATA_SCHEMAS.md)
- [AI Story and Validation](./AI_STORY_VALIDATION.md)

## Core Idea

Use chunks and grid data internally, but render the world organically.

The world must not look like visible square blocks. Use smooth masks, curves, splines, blended terrain, irregular structure footprints, and decoration scatter.

## Generation Pipeline

```text
1. Create seed
2. Generate control fields
3. Generate height, moisture, heat, and power maps
4. Decide biomes
5. Generate rivers and lakes
6. Generate cave and underground candidates
7. Generate sky and floating island candidates
8. Place major structures with reservations
9. Place entrances and exits
10. Place roads, bridges, farms, and resources
11. Run overlap validation
12. Run repair passes
13. Add factions, NPCs, conflicts, and storyboard hooks
14. Save base world
```

## Noise Maps

Use multiple noise maps:

| Map | Purpose |
|---|---|
| Height | ocean, plains, hills, mountains |
| Moisture | desert, grassland, forest, swamp |
| Heat | snow, temperate, tropical |
| Water flow | rivers, lakes, waterfalls |
| Cave | underground openings and tunnels |
| Sky | possible floating islands |
| Danger | monster and dungeon risk |
| Civilization | towns, roads, farms |
| Power maps | Magic, Aura, Alchemy, Mechanical, Biological, Mind |

Noise creates possibility. Rules decide final placement.

## Natural Visual Style

Internal chunks can be square. Visible terrain should be organic.

Use:

- biome masks
- splines for roads and rivers
- irregular polygons for forests
- soft edge blending
- texture decals
- elevation shadows
- object scatter with spacing rules
- large structure footprints

Avoid:

- visible block borders
- square rivers
- farms placed randomly
- roads with sharp unnatural turns
- forests arranged like perfect rectangles

## Structure Placement

Every major structure needs:

```text
id
type
layer
footprint
influence_zone
exclusion_zone
entrances
owner_faction
power_influence
story_hooks
```

Large structures must place before small decorations.

Priority order:

```text
1. Critical story structures
2. Major geography
3. Settlements and castles
4. Required entrances and roads
5. Dungeons and ruins
6. Farms and resources
7. Forests and vegetation
8. NPCs, monsters, loot
9. Decorations
```

## Entrances Between Layers

Every cave, dungeon, mine, basement, or sewer needs an entrance contract.

```text
Surface cave mouth
  -> underground cave spawn point
  -> return exit
```

The validator must reject underground playable spaces that have no entrance unless they are marked as sealed future content.

## Overlap Rule

Visual overlap is allowed. Gameplay overlap must be validated.

Good overlap:

- vines on ruins
- grass blending into roads
- floating island shadow over lake
- fog near cave mouth

Bad overlap:

- cave door blocked by tree
- farm inside lake
- castle wall through river with no bridge/moat rule
- player spawn inside wall
- dungeon with no exit

## Repair Pass Examples

The repair system can:

- move decorations away from paths
- clear trees from castle courtyards
- add a bridge where a road crosses a river
- reroute a road around a lake
- convert lake-edge farms into rice fields or fish farms
- carve a slope to an entrance
- move a cave mouth out from under a building

