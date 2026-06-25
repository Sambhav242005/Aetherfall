# Stage 2 / Sub-project 1 Design — Deterministic Noise Engine

**Date:** 2026-06-25
**Status:** Approved (brainstorming complete)
**Scope:** Sub-project **#1 of 3** in Stage 2. This sub-project only: real, seamless,
seedable terrain fields + biome classification + chunk integration. **No AI, no story
control, no renderer, no structure placement** — those are sub-projects #2 and #3.

---

## 1. Problem

Stage 2 makes the world **fully procedural from story** (chosen during brainstorming):
`World Bible → World Plan → noise engine → placement → persist → story → renderer`.
Everything downstream needs a real terrain substrate first. Today there is none:

- `chunk_manager.py` seeds a **fresh RNG per chunk** (`sha256(seed:cx:cy:…)`), which
  mathematically *guarantees a seam at every chunk border* and makes per-cell
  `elevation`/`moisture` **white noise** (no spatially-coherent terrain).
- `biome` comes from a hardcoded `RIVERFALL_CHUNKS` dict (10 fixed chunks); everything
  off-map is `"plains"`.
- `power_influence` (6 principles) and `danger_level` are a single `random()` per chunk.

**This sub-project replaces that with a deterministic, spatially-coherent, seamless field
engine.** The single most important correctness property: **every field is a continuous
function of GLOBAL world coordinates**; a chunk is just a 64×64 sampling window into that
global field, so seamlessness holds *by construction* and is directly testable.

## 2. Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Stage-2 world model | **Fully procedural from story** (terrain *and* structure placement regenerated). Structure placement is sub-project #2; this is #1. |
| Build order | **#1 noise engine → #2 AI world-plan + placement → #3 browser map renderer.** Each its own spec → plan → implement cycle. |
| Engine approach | **A — MVP coherent fields.** Pure-Python seedable fBm over global coords; surface-complete; ridged-noise river *hints* (no flow simulation). |
| Hydrology | **Cosmetic river hints only.** Real flow-accumulation (option B) deferred. |
| Performance | **Pure Python.** NumPy vectorization (option C) deferred as a drop-in upgrade (mirrors the codebase's "NumPy brute-force now, `sqlite-vec` later" precedent). |
| Schema | **No Pydantic schema change.** `terrain_cells` is `list[dict[str, Any]]`, enriched additively; `Chunk` shape unchanged. |
| `world_generator.py` | **Untouched.** Hand-authored Riverfall stays; structures are reconciled with terrain in #2. |
| Layer scope | **Surface done fully**; sky/underground/deep/ocean get a *minimal* coherent field. Matches the roadmap's Phase-2 "surface layer only". |

### Acknowledged temporary limitation
After #1, hand-authored structure positions (e.g. `struct_moonlake` at (500,400)) are
**not** aligned with the noise terrain under them. This is expected: #2 reconciles them
(places structures *by* terrain), and nothing renders until #3. #1 is validated purely on
field/biome/chunk correctness, not on structure-terrain agreement.

## 3. Context: existing code

- `engine/chunk_manager.py` — `generate_chunk(world_id, seed, layer, cx, cy) -> Chunk`,
  `CHUNK_SIZE = 64`. **Rewritten** here. The `RIVERFALL_CHUNKS` dict and per-cell
  `rng.random()` are removed.
- `engine/world_generator.py` — hand-authored Riverfall. **Unchanged.**
- `engine/overlap_validator.py` — structure overlap validation. **Unchanged** (used by #2).
- `models/schemas.py::Chunk` — `terrain_cells: list[dict[str, Any]]`,
  `power_influence: dict[str, float]`, `danger_level: float`. **Unchanged.**
- `api/routes_world.py` — `GET /api/world/{id}/chunk/{layer}/{cx}/{cy}` calls
  `generate_chunk`. **Unchanged** (returns the richer cells transparently).
- `config.py` — `pydantic-settings`. Terrain tunables live as **named module constants**
  in the engine (domain constants, not ops/env knobs), not in `config.py`.
- Tests — `tests/test_generation.py` already asserts same-seed determinism for
  `generate_chunk`. These **must stay green**.

## 4. Module layout (`backend/app/engine/`)

```
noise.py    # NEW  pure math: integer hash, value_noise, fbm. No domain knowledge.
fields.py   # NEW  WorldFields(seed) facade: per-channel salted-fBm samplers.
biomes.py   # NEW  classify(h, m, heat) -> biome; thresholds; BIOMES; color palette.
chunk_manager.py  # REWRITE  sample WorldFields per cell -> build Chunk (shape unchanged).
```

Each module is independently testable: `noise` (math only), `fields` (channel decorrelation
+ ranges), `biomes` (pure classification), `chunk_manager` (integration + determinism).

## 5. Noise core (`noise.py`)

Deterministic, no RNG state, no wall-clock, cross-platform.

- **Integer lattice hash** with a splitmix64 finalizer, all arithmetic masked to 64 bits
  (`& 0xFFFFFFFFFFFFFFFF`), returning a float in `[0, 1)`:

  ```
  MASK64 = 0xFFFFFFFFFFFFFFFF
  def _hash01(seed, salt, ix, iy):
      h = (ix & MASK64) * 0x1F1F1F1F1F1F1F1F
      h = (h ^ ((iy & MASK64) * 0x9E3779B97F4A7C15)) & MASK64
      h = (h ^ seed ^ salt) & MASK64
      h = ((h ^ (h >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
      h = ((h ^ (h >> 27)) * 0x94D049BB133111EB) & MASK64
      h ^= h >> 31
      return (h & 0xFFFFFFFF) / 0x100000000   # [0, 1)
  ```

- **Value noise** `value_noise(seed, salt, x, y)`: hash the 4 integer-lattice corners
  surrounding `(x, y)`, bilinearly blend using Perlin's **quintic fade**
  `f(t) = 6t⁵ − 15t⁴ + 10t³` on the fractional part (smooth 1st/2nd derivatives → no grid
  artifacts). Output `[0, 1]`.

- **fBm** `fbm(seed, salt, x, y, *, octaves=4, lacunarity=2.0, gain=0.5, frequency)`:
  ```
  total, amp, freq, norm = 0, 1, frequency, 0
  for _ in range(octaves):
      total += amp * value_noise(seed, salt + octave_index, x*freq, y*freq)
      norm  += amp
      freq  *= lacunarity
      amp   *= gain
  return total / norm     # normalized to [0, 1]
  ```
  (Per-octave salt offset decorrelates octaves.) Callers `round(value, 4)`.

## 6. Fields (`fields.py`)

`WorldFields(seed: int, modifiers: tuple = ())`. **`modifiers` is an unused forward hook
for #2** (see §12); in #1 it is always empty ⇒ pure base field. Channels carry distinct
integer salts so they are decorrelated. `frequency = 1 / feature_size`.

| Method | Salt name | feature_size | octaves | Returns |
|---|---|---|---|---|
| `height(gx, gy)` | `SALT_HEIGHT` | 256 | 5 | `float [0,1]` |
| `moisture(gx, gy)` | `SALT_MOISTURE` | 200 | 4 | `float [0,1]` |
| `heat(gx, gy)` | `SALT_HEAT` | 320 | 3 | `float [0,1]` |
| `flow(gx, gy)` | `SALT_FLOW` | 180 | 4 | `float [0,1]` |
| `power(gx, gy)` | `SALT_POWER_*` ×6 | 220 | 2 | `dict[str,float]` keys: magic, aura, alchemy, mechanical, biological, mind |
| `danger(gx, gy)` | `SALT_DANGER` | 220 | 2 | `float [0,1]` |
| `civilization(gx, gy)` | `SALT_CIV` | 220 | 2 | `float [0,1]` |

Salts are fixed distinct constants (e.g. `0x48..`, `0x4D..`, …); the 6 power salts are 6
distinct constants. All outputs `round(_, 4)`.

## 7. Biomes (`biomes.py`)

Thresholds (module constants, tunable):

```
SEA_LEVEL  = 0.38     # below -> water
BEACH      = 0.42     # coastal sand band
MOUNTAIN   = 0.72     # rock
SNOW_PEAK  = 0.85     # snow-capped
HEAT_COLD  = 0.25
HEAT_WARM  = 0.60
```

`classify(height, moisture, heat) -> str`:

```
height >= SNOW_PEAK            -> "snow_peak"
height >= MOUNTAIN            -> "mountain"
height <  SEA_LEVEL           -> "ocean"
height <  BEACH               -> "beach"
else (lowland/hill):
  heat < HEAT_COLD:  moisture < 0.40 -> "tundra"        else -> "taiga"
  heat < HEAT_WARM:  moisture < 0.25 -> "shrubland"
                     moisture < 0.55 -> "grassland"
                     moisture < 0.80 -> "forest"        else -> "swamp"
  else (hot):        moisture < 0.20 -> "desert"
                     moisture < 0.50 -> "savanna"
                     moisture < 0.80 -> "tropical_forest" else -> "rainforest"
```

Also: `is_water(height) -> bool` (`height < SEA_LEVEL`), a `BIOMES: frozenset[str]`
registry of **every biome the engine emits** — the 14 surface biomes above + `"river"`
(applied in §8) + the 6 minimal non-surface biomes (`void`, `floating_island`, `rock`,
`cavern`, `deep_water`, `trench`; see §9) = **21 total** — and a `PALETTE: dict[str, str]`
biome→hex map covering all of `BIOMES`. `PALETTE` is **defined now but consumed by #3**
(the renderer); keeping it here makes this module the single source of truth for the
biome→color mapping.

## 8. Rivers (cosmetic, seamless)

A surface cell is a **river** when:

```
SEA_LEVEL <= height < MOUNTAIN   AND   abs(flow - 0.5) < RIVER_WIDTH   # RIVER_WIDTH = 0.015
```

River cells override `biome = "river"` and set `water = True`. This yields winding bands
from the `flow` channel — no flow accumulation, no global state, fully per-cell and
seamless. Real hydrology is deferred (option B, §13).

## 9. Chunk integration (`chunk_manager.py`)

`CHUNK_SIZE = 64` unchanged. `generate_chunk(world_id, seed, layer, cx, cy) -> Chunk`:

1. `fields = WorldFields(seed)` (cheap; may be `lru_cache`-d by seed).
2. For each of the 64×64 cells, `gx, gy = cx*64 + x, cy*64 + y`.
   - **Surface:** sample `height/moisture/heat/flow`; `water = is_water(height)`;
     `river = is_river(...)`; `biome = "river" if river else classify(h, m, heat)`. Cell:
     `{"x": gx, "y": gy, "elevation": h, "moisture": m, "heat": heat, "biome": biome, "water": water or river}`.
   - **Sky / underground / deep / ocean (minimal):** one coherent channel → two biomes
     each (sky → `void`/`floating_island`; underground & deep → `rock`/`cavern`;
     ocean → `deep_water`/`trench`). Cells carry `elevation` + `biome` + `water`; `heat`/
     `moisture` may be `0.0`. Marked minimal by design.
3. `chunk.biome` = **modal** biome across cells (single backward-compat label).
4. `chunk.power_influence = fields.power(center_gx, center_gy)` (6 floats).
   `chunk.danger_level = fields.danger(center_gx, center_gy)`.
5. Return `Chunk(...)` — **identical schema**, richer contents.

Per-cell payload stays light (no per-cell power×6); power/danger remain per-chunk, now
coherent. Chunk JSON size is unchanged in cardinality (4096 cells), with two extra scalar
keys per cell.

## 10. Determinism & seamlessness contract

- `value_noise` / `fbm` / every `WorldFields` method depend **only** on their arguments.
  No global RNG, no time, no I/O. 64-bit-masked integer math ⇒ cross-platform stable.
- A chunk's cells are **direct samples of the global field at global coords** ⇒ adjacent
  chunks share the field ⇒ **no seam**.
- All field outputs `round(_, 4)` so equality-based tests are robust.

## 11. Testing strategy

New `tests/test_noise.py`; extend `tests/test_generation.py`. All offline, no network.

**`noise.py`** — output in `[0,1]`; determinism (same args → identical); neighbor
continuity (`|f(x) − f(x+1)|` below a smoothness epsilon); different `seed`/`salt` differ;
fBm stays normalized across a sweep of samples.

**`fields.py`** — every channel in `[0,1]`; `power()` returns the 6 expected keys; channels
are decorrelated (height ≠ moisture at the same point for most samples).

**`biomes.py`** — `classify` on hand-picked `(h,m,heat)` triples → expected biome; water
below `SEA_LEVEL`; `snow_peak` only when high; every `classify` output ∈ `BIOMES` (it emits
the 14 surface biomes); `PALETTE` covers all 21 `BIOMES`.

**`chunk_manager.py`** — same seed+coords → identical chunk (existing test stays green);
different positions differ; cells carry `heat` + `water`; `power_influence` has 6 keys;
`chunk.biome ∈ BIOMES`; **seamlessness**: a chunk's edge cell at `(gx,gy)` equals a
standalone `WorldFields(seed).height(gx,gy)` sample (exact equality — the chunk is a
faithful window), and the cross-chunk neighbor delta `|height(63,y) − height(64,y)|` is
below a continuity epsilon (start `ε = 0.2`, tighten empirically); **distribution sanity**
over a large region: >1 distinct biome appears and the water fraction is within a sane band
(5–60%).

**Regression** — all existing `tests/test_generation.py` assertions pass unchanged
(`generate_world` is untouched).

## 12. Forward hooks for #2 (designed here, built later)

- **`Modifier` protocol** — `WorldFields(seed, modifiers=())` accepts a tuple of objects
  with signature `apply(channel: str, gx: float, gy: float, base: float) -> float`. #2 uses
  these to bias fields near planned structures/regions (raise `height` for a planned
  mountain range, raise `moisture` for a planned swamp, raise `civilization` near a planned
  town). **Not implemented in #1** — the parameter exists, defaults empty, and is a no-op.
- **`PALETTE`** (biome→hex) is the renderer's (#3) color source of truth.
- A future **region-snapshot endpoint** (downsampled field grid for fast pan/zoom) is noted
  for #3, not built here.

## 13. Out of scope (this sub-project)

- AI / story control of the fields (**#2**).
- Structure placement by terrain, reservations, repair, NPC/faction re-grounding (**#2**).
- The browser map renderer (**#3**).
- Real flow-accumulation hydrology (**option B** — future refinement).
- NumPy vectorization (**option C** — future drop-in upgrade).
- Ocean-vs-lake distinction, roads/civilization placement, rich non-surface layers.
