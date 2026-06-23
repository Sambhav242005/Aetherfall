# AI Story and Validation

See also:

- [Product Spec](./PRODUCT_SPEC.md)
- [World Generation](./WORLD_GENERATION.md)
- [Data Schemas](./DATA_SCHEMAS.md)
- [Evaluation Checklist](./EVALUATION_CHECKLIST.md)

## Role of AI

AI is a creative assistant, not the game authority.

AI can propose:

- dialogue
- rumors
- storyboard cards
- quest ideas
- scene descriptions
- structure concepts
- faction conflict ideas
- NPC personality details

AI cannot directly change:

- inventory
- damage
- NPC death
- faction ownership
- quest completion
- map geometry
- structure placement
- canonical world state

## Proposal Flow

```text
AI proposal
  -> schema validation
  -> world fact check
  -> contradiction check
  -> gameplay rule check
  -> approval
  -> canonical state update
```

## Storyboard System

Storyboard is the planning layer between raw AI story and playable game content.

A storyboard card should define:

```text
scene_id
location_id
characters_present
camera_or_view
visual_focus
mood
gameplay_objective
environment_details
revealed_information
player_feeling
validation_requirements
```

Example:

```text
Scene: First view of Moonlake
Location: Moonlake overlook
Characters: sick farmer, village guard
Camera: wide 2.5D view from hill path
Visual focus: glowing blue lake below floating island
Mood: beautiful but disturbing
Gameplay: inspect dead fish near shore
Reveal: lake changed after old castle drain opened
```

## Validation Questions

Before accepting an AI proposal:

- Does this location exist?
- Are the characters alive and present?
- Is the player allowed to know this information?
- Does the proposed event contradict previous choices?
- Is the location reachable?
- Does the event require an object that does not exist?
- Does the quest have a valid objective and completion rule?
- Does it mutate state directly instead of proposing a valid action?

## AI Prompting Rule

All AI responses should be structured JSON when used by the engine.

Do not let the AI return free-form text for engine-changing operations.

Free-form text is allowed only for display-only content such as approved dialogue lines or scene flavor.

