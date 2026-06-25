# Deterministic Noise Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-chunk-random terrain in `chunk_manager.py` with a real, seamless, seedable noise engine (coherent fields → biomes → chunks), with no Pydantic schema change.

**Architecture:** Three new pure modules — `noise.py` (math), `fields.py` (`WorldFields` channel facade), `biomes.py` (classification + registry) — composed by a rewritten `chunk_manager.py`. Every field is a function of **global** world coordinates, so a chunk is just a 64×64 sampling window and seamlessness holds by construction. No AI, no story control, no renderer, no structure placement (those are Stage-2 sub-projects #2 and #3).

**Tech Stack:** Python 3, pure standard library (`math`, `collections.Counter`), pytest. No new dependencies. (NumPy exists in the project but is intentionally not used here — vectorization is a deferred upgrade.)

**Spec:** `docs/superpowers/specs/2026-06-25-stage2-noise-engine-design.md`

**Branch:** Implement on a fresh `feat/stage2-noise-engine` branch (the execution skill creates the worktree/branch). The current `feat/stage1-story-rag` branch has unrelated uncommitted WIP.

## Global Constraints

Every task implicitly includes these (copied verbatim from the spec):

- **Pure Python, no new dependencies.** Do not import numpy in `noise.py`/`fields.py`/`biomes.py`/`chunk_manager.py`.
- **No Pydantic schema change.** `Chunk` keeps its exact shape: `terrain_cells: list[dict]`, `power_influence: dict[str, float]`, `danger_level: float`. Enrich cells additively only.
- **`backend/app/engine/world_generator.py` is NOT touched.**
- **Determinism:** every field/noise function depends only on its arguments (no global RNG, no wall clock, no I/O). All 64-bit integer math is masked with `& 0xFFFFFFFFFFFFFFFF`. **All field outputs are `round(value, 4)`.**
- **Range:** every noise/field output is in `[0, 1]`.
- **Surface layer is done fully; sky/underground/deep/ocean get a minimal coherent field.**
- **All existing `backend/tests/test_generation.py` assertions must stay green** (run from `backend/` with `python -m pytest`).

---

### Task 1: Noise core (`noise.py`)

**Files:**
- Create: `backend/app/engine/noise.py`
- Test: `backend/tests/test_noise.py`

**Interfaces:**
- Consumes: nothing (standard library only).
- Produces:
  - `value_noise(seed: int, salt: int, x: float, y: float) -> float` — coherent value noise in `[0, 1]`.
  - `fbm(seed: int, salt: int, x: float, y: float, *, octaves: int = 4, lacunarity: float = 2.0, gain: float = 0.5, frequency: float = 1.0) -> float` — fractional Brownian motion, normalized to `[0, 1]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_noise.py`:

```python
from app.engine.noise import value_noise, fbm


class TestValueNoise:
    def test_in_range(self):
        for i in range(200):
            v = value_noise(42, 1, i * 0.37, i * 0.61)
            assert 0.0 <= v <= 1.0

    def test_deterministic(self):
        assert value_noise(42, 1, 3.5, 2.25) == value_noise(42, 1, 3.5, 2.25)

    def test_continuous(self):
        # A tiny spatial step produces a tiny change (smooth function).
        a = value_noise(7, 1, 3.5, 2.5)
        b = value_noise(7, 1, 3.5 + 1e-3, 2.5)
        assert abs(a - b) < 1e-2

    def test_varies_with_seed_and_salt(self):
        base = value_noise(1, 1, 5.5, 5.5)
        assert value_noise(2, 1, 5.5, 5.5) != base
        assert value_noise(1, 2, 5.5, 5.5) != base

    def test_negative_coords_deterministic(self):
        assert value_noise(9, 3, -4.5, -2.5) == value_noise(9, 3, -4.5, -2.5)
        assert 0.0 <= value_noise(9, 3, -4.5, -2.5) <= 1.0


class TestFbm:
    def test_in_range(self):
        for i in range(200):
            v = fbm(42, 1, i * 1.3, i * 0.7, octaves=5, frequency=1 / 64)
            assert 0.0 <= v <= 1.0

    def test_deterministic(self):
        a = fbm(42, 1, 10.0, 20.0, octaves=4, frequency=1 / 32)
        b = fbm(42, 1, 10.0, 20.0, octaves=4, frequency=1 / 32)
        assert a == b

    def test_single_octave_equals_value_noise(self):
        # One octave with frequency 1.0 reduces to plain value noise.
        assert fbm(42, 5, 3.3, 4.4, octaves=1, frequency=1.0) == value_noise(42, 5, 3.3, 4.4)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_noise.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine.noise'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/engine/noise.py`:

```python
from __future__ import annotations
import math

MASK64 = 0xFFFFFFFFFFFFFFFF


def _hash01(seed: int, salt: int, ix: int, iy: int) -> float:
    """Deterministic hash of an integer lattice point -> float in [0, 1).

    splitmix64-style finalizer; all arithmetic masked to 64 bits for
    cross-platform stability. No RNG state, no wall clock.
    """
    h = ((ix & MASK64) * 0x1F1F1F1F1F1F1F1F) & MASK64
    h = (h ^ ((iy & MASK64) * 0x9E3779B97F4A7C15)) & MASK64
    h = (h ^ (seed & MASK64) ^ (salt & MASK64)) & MASK64
    h = ((h ^ (h >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    h = ((h ^ (h >> 27)) * 0x94D049BB133111EB) & MASK64
    h ^= h >> 31
    return (h & 0xFFFFFFFF) / 0x100000000  # [0, 1)


def _fade(t: float) -> float:
    """Perlin quintic smoothstep: 6t^5 - 15t^4 + 10t^3."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def value_noise(seed: int, salt: int, x: float, y: float) -> float:
    """Coherent value noise in [0, 1] at continuous (x, y)."""
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy

    v00 = _hash01(seed, salt, ix, iy)
    v10 = _hash01(seed, salt, ix + 1, iy)
    v01 = _hash01(seed, salt, ix, iy + 1)
    v11 = _hash01(seed, salt, ix + 1, iy + 1)

    u = _fade(fx)
    v = _fade(fy)
    return _lerp(_lerp(v00, v10, u), _lerp(v01, v11, u), v)


def fbm(seed: int, salt: int, x: float, y: float, *, octaves: int = 4,
        lacunarity: float = 2.0, gain: float = 0.5, frequency: float = 1.0) -> float:
    """Fractional Brownian motion: sum of octaves, normalized to [0, 1]."""
    total = 0.0
    amplitude = 1.0
    freq = frequency
    norm = 0.0
    for octave in range(octaves):
        total += amplitude * value_noise(seed, salt + octave, x * freq, y * freq)
        norm += amplitude
        freq *= lacunarity
        amplitude *= gain
    return total / norm if norm else 0.0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_noise.py -v`
Expected: PASS (all `TestValueNoise` and `TestFbm` tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/noise.py backend/tests/test_noise.py
git commit -m "feat(engine): seedable value-noise + fBm core (stage2 #1)"
```

---

### Task 2: Biome classification (`biomes.py`)

**Files:**
- Create: `backend/app/engine/biomes.py`
- Test: `backend/tests/test_biomes.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - Constants: `SEA_LEVEL=0.38`, `BEACH=0.42`, `MOUNTAIN=0.72`, `SNOW_PEAK=0.85`, `HEAT_COLD=0.25`, `HEAT_WARM=0.60`, `RIVER_WIDTH=0.015`.
  - `is_water(height: float) -> bool`
  - `is_river(flow: float, height: float) -> bool`
  - `classify(height: float, moisture: float, heat: float) -> str`
  - `BIOMES: frozenset[str]` (21 members) and `PALETTE: dict[str, str]` (covers all of `BIOMES`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_biomes.py`:

```python
from app.engine.biomes import (
    classify, is_water, is_river, BIOMES, PALETTE,
    SEA_LEVEL, MOUNTAIN, SNOW_PEAK,
)


class TestClassify:
    def test_ocean_below_sea_level(self):
        assert classify(0.20, 0.5, 0.5) == "ocean"

    def test_beach_just_above_sea_level(self):
        assert classify(0.40, 0.5, 0.5) == "beach"

    def test_mountain_and_snow(self):
        assert classify(0.75, 0.5, 0.5) == "mountain"
        assert classify(0.90, 0.5, 0.2) == "snow_peak"

    def test_cold_lowland(self):
        assert classify(0.55, 0.30, 0.10) == "tundra"
        assert classify(0.55, 0.60, 0.10) == "taiga"

    def test_temperate_lowland(self):
        assert classify(0.55, 0.10, 0.45) == "shrubland"
        assert classify(0.55, 0.40, 0.45) == "grassland"
        assert classify(0.55, 0.70, 0.45) == "forest"
        assert classify(0.55, 0.90, 0.45) == "swamp"

    def test_hot_lowland(self):
        assert classify(0.55, 0.10, 0.80) == "desert"
        assert classify(0.55, 0.35, 0.80) == "savanna"
        assert classify(0.55, 0.70, 0.80) == "tropical_forest"
        assert classify(0.55, 0.95, 0.80) == "rainforest"

    def test_every_output_is_a_known_biome(self):
        for h in (0.1, 0.4, 0.55, 0.75, 0.9):
            for m in (0.1, 0.3, 0.6, 0.9):
                for t in (0.1, 0.45, 0.8):
                    assert classify(h, m, t) in BIOMES


class TestWaterAndRiver:
    def test_is_water(self):
        assert is_water(SEA_LEVEL - 0.01) is True
        assert is_water(SEA_LEVEL) is False

    def test_is_river_center_band_on_land(self):
        assert is_river(0.5, 0.55) is True       # flow near 0.5, land height

    def test_is_river_excludes_water_and_mountain(self):
        assert is_river(0.5, 0.20) is False       # underwater
        assert is_river(0.5, 0.90) is False       # mountain
        assert is_river(0.9, 0.55) is False       # flow far from 0.5


class TestRegistry:
    def test_biomes_count(self):
        assert len(BIOMES) == 21

    def test_palette_covers_every_biome(self):
        assert set(PALETTE) == set(BIOMES)
        for color in PALETTE.values():
            assert color.startswith("#") and len(color) == 7
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_biomes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine.biomes'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/engine/biomes.py`:

```python
from __future__ import annotations

# --- elevation thresholds (height in [0, 1]) ---
SEA_LEVEL = 0.38
BEACH = 0.42
MOUNTAIN = 0.72
SNOW_PEAK = 0.85

# --- climate thresholds ---
HEAT_COLD = 0.25
HEAT_WARM = 0.60

# --- river hint width ---
RIVER_WIDTH = 0.015

_SURFACE_BIOMES = (
    "snow_peak", "mountain", "ocean", "beach",
    "tundra", "taiga", "shrubland", "grassland", "forest", "swamp",
    "desert", "savanna", "tropical_forest", "rainforest",
)
_NONSURFACE_BIOMES = ("void", "floating_island", "rock", "cavern", "deep_water", "trench")

BIOMES = frozenset(_SURFACE_BIOMES + ("river",) + _NONSURFACE_BIOMES)

# Canonical biome -> color map. Defined here (single source of truth); consumed
# by the Stage-2 #3 browser renderer.
PALETTE: dict[str, str] = {
    "snow_peak": "#f4f7fb",
    "mountain": "#8a8276",
    "ocean": "#2b6c8f",
    "beach": "#e6d7a8",
    "tundra": "#cdd6cf",
    "taiga": "#5f7a5a",
    "shrubland": "#b7b066",
    "grassland": "#8fb05a",
    "forest": "#4f8a4b",
    "swamp": "#5d6b3e",
    "desert": "#e2c789",
    "savanna": "#c9b35e",
    "tropical_forest": "#3f8f5a",
    "rainforest": "#2f7d50",
    "river": "#3d8fb0",
    "void": "#0c1020",
    "floating_island": "#7a86c2",
    "rock": "#6b6358",
    "cavern": "#3a3530",
    "deep_water": "#16314a",
    "trench": "#0d1c2c",
}


def is_water(height: float) -> bool:
    return height < SEA_LEVEL


def is_river(flow: float, height: float) -> bool:
    """Cosmetic river hint: a winding band of the flow field over land."""
    return SEA_LEVEL <= height < MOUNTAIN and abs(flow - 0.5) < RIVER_WIDTH


def classify(height: float, moisture: float, heat: float) -> str:
    """Map (height, moisture, heat) in [0,1]^3 to a surface biome."""
    if height >= SNOW_PEAK:
        return "snow_peak"
    if height >= MOUNTAIN:
        return "mountain"
    if height < SEA_LEVEL:
        return "ocean"
    if height < BEACH:
        return "beach"
    if heat < HEAT_COLD:
        return "tundra" if moisture < 0.40 else "taiga"
    if heat < HEAT_WARM:
        if moisture < 0.25:
            return "shrubland"
        if moisture < 0.55:
            return "grassland"
        if moisture < 0.80:
            return "forest"
        return "swamp"
    if moisture < 0.20:
        return "desert"
    if moisture < 0.50:
        return "savanna"
    if moisture < 0.80:
        return "tropical_forest"
    return "rainforest"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_biomes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/biomes.py backend/tests/test_biomes.py
git commit -m "feat(engine): biome classifier + BIOMES/PALETTE registry (stage2 #1)"
```

---

### Task 3: World fields (`fields.py`)

**Files:**
- Create: `backend/app/engine/fields.py`
- Test: `backend/tests/test_fields.py`

**Interfaces:**
- Consumes: `app.engine.noise.fbm`.
- Produces:
  - `POWER_PRINCIPLES: tuple[str, ...]` = `("magic", "aura", "alchemy", "mechanical", "biological", "mind")`.
  - `class WorldFields:` constructed `WorldFields(seed: int, modifiers: tuple = ())` with methods, each returning a `round(_, 4)` value in `[0,1]`:
    `height(gx, gy)`, `moisture(gx, gy)`, `heat(gx, gy)`, `flow(gx, gy)`, `danger(gx, gy)`, `civilization(gx, gy)` → `float`; `power(gx, gy)` → `dict[str, float]` (the 6 `POWER_PRINCIPLES` keys).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_fields.py`:

```python
from app.engine.fields import WorldFields, POWER_PRINCIPLES


class TestWorldFields:
    def test_scalar_channels_in_range(self):
        f = WorldFields(2026)
        for gx in range(0, 500, 23):
            for name in ("height", "moisture", "heat", "flow", "danger", "civilization"):
                v = getattr(f, name)(gx, gx * 0.5)
                assert 0.0 <= v <= 1.0

    def test_power_has_six_named_keys(self):
        p = WorldFields(2026).power(100, 100)
        assert tuple(p.keys()) == POWER_PRINCIPLES
        for v in p.values():
            assert 0.0 <= v <= 1.0

    def test_deterministic(self):
        a, b = WorldFields(7), WorldFields(7)
        assert a.height(50, 60) == b.height(50, 60)
        assert a.power(50, 60) == b.power(50, 60)

    def test_channels_decorrelated(self):
        # Different salted channels must not be the same field.
        f = WorldFields(7)
        diffs = sum(1 for gx in range(0, 400, 7) if f.height(gx, gx) != f.moisture(gx, gx))
        assert diffs > 50

    def test_different_seed_differs(self):
        assert WorldFields(1).height(10, 10) != WorldFields(2).height(10, 10)

    def test_outputs_rounded_to_4dp(self):
        v = WorldFields(7).height(13, 17)
        assert round(v, 4) == v

    def test_modifiers_default_empty(self):
        # Forward hook for sub-project #2; unused here.
        assert WorldFields(7).modifiers == ()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_fields.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine.fields'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/engine/fields.py`:

```python
from __future__ import annotations
from app.engine.noise import fbm

POWER_PRINCIPLES = ("magic", "aura", "alchemy", "mechanical", "biological", "mind")

# Distinct per-channel salts so channels are decorrelated.
SALT_HEIGHT = 0x48454947
SALT_MOISTURE = 0x4D4F4953
SALT_HEAT = 0x48454154
SALT_FLOW = 0x464C4F57
SALT_DANGER = 0x44414E47
SALT_CIV = 0x43495649
SALT_POWER = (0x504D4147, 0x50415552, 0x50414C43, 0x504D4543, 0x5042494F, 0x504D494E)


def _freq(feature_size: float) -> float:
    return 1.0 / feature_size


class WorldFields:
    """Coherent global terrain fields bound to a world seed.

    Every method is a pure function of (seed, global x, global y). `modifiers`
    is a forward hook for Stage-2 sub-project #2 (story-biased fields); it is
    unused here and defaults to empty (a no-op base field).
    """

    def __init__(self, seed: int, modifiers: tuple = ()):
        self.seed = int(seed)
        self.modifiers = tuple(modifiers)

    def height(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_HEIGHT, gx, gy, octaves=5, frequency=_freq(256)), 4)

    def moisture(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_MOISTURE, gx, gy, octaves=4, frequency=_freq(200)), 4)

    def heat(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_HEAT, gx, gy, octaves=3, frequency=_freq(320)), 4)

    def flow(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_FLOW, gx, gy, octaves=4, frequency=_freq(180)), 4)

    def danger(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_DANGER, gx, gy, octaves=2, frequency=_freq(220)), 4)

    def civilization(self, gx: float, gy: float) -> float:
        return round(fbm(self.seed, SALT_CIV, gx, gy, octaves=2, frequency=_freq(220)), 4)

    def power(self, gx: float, gy: float) -> dict[str, float]:
        return {
            name: round(fbm(self.seed, salt, gx, gy, octaves=2, frequency=_freq(220)), 4)
            for name, salt in zip(POWER_PRINCIPLES, SALT_POWER)
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_fields.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/fields.py backend/tests/test_fields.py
git commit -m "feat(engine): WorldFields channel facade over fBm (stage2 #1)"
```

---

### Task 4: Chunk integration (`chunk_manager.py` rewrite)

**Files:**
- Modify (rewrite): `backend/app/engine/chunk_manager.py`
- Test: `backend/tests/test_chunk_manager.py`
- Verify-only (do not edit): `backend/tests/test_generation.py`

**Interfaces:**
- Consumes: `WorldFields` (Task 3); `classify`, `is_water`, `is_river`, `BIOMES` (Task 2).
- Produces: `generate_chunk(world_id: str, seed: int, layer: Layer, cx: int, cy: int) -> Chunk` (same signature as before; `Chunk` schema unchanged). `CHUNK_SIZE = 64` is preserved.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_chunk_manager.py`:

```python
from app.engine.chunk_manager import generate_chunk, CHUNK_SIZE
from app.engine.fields import WorldFields, POWER_PRINCIPLES
from app.engine.biomes import BIOMES, SEA_LEVEL
from app.models.schemas import Layer

WID = "world-test"
SEED = 31337


def _surface_chunk(cx=0, cy=0):
    return generate_chunk(WID, SEED, Layer.SURFACE, cx, cy)


class TestChunkShape:
    def test_cell_count_and_new_keys(self):
        chunk = _surface_chunk()
        assert len(chunk.terrain_cells) == CHUNK_SIZE * CHUNK_SIZE
        cell = chunk.terrain_cells[0]
        for key in ("x", "y", "elevation", "moisture", "heat", "biome", "water"):
            assert key in cell

    def test_power_influence_has_six_keys(self):
        chunk = _surface_chunk()
        assert tuple(chunk.power_influence.keys()) == POWER_PRINCIPLES

    def test_chunk_biome_is_known(self):
        assert _surface_chunk().biome in BIOMES

    def test_cell_biomes_are_known(self):
        for cell in _surface_chunk().terrain_cells:
            assert cell["biome"] in BIOMES


class TestDeterminismAndSeams:
    def test_same_seed_same_chunk(self):
        a = _surface_chunk()
        b = _surface_chunk()
        assert [c["elevation"] for c in a.terrain_cells] == [c["elevation"] for c in b.terrain_cells]
        assert a.power_influence == b.power_influence

    def test_chunk_is_faithful_window_into_global_field(self):
        # The cell at local (x=63, y=10) holds global (63, 10); it must equal a
        # standalone field sample at that global coord (seamless by construction).
        chunk = _surface_chunk(0, 0)
        cell = chunk.terrain_cells[10 * CHUNK_SIZE + 63]
        assert cell["x"] == 63 and cell["y"] == 10
        assert cell["elevation"] == WorldFields(SEED).height(63, 10)

    def test_border_is_continuous(self):
        f = WorldFields(SEED)
        # gx=63 (right edge of chunk 0) and gx=64 (left edge of chunk 1) are adjacent.
        assert abs(f.height(64, 10) - f.height(63, 10)) < 0.2

    def test_different_positions_differ(self):
        assert _surface_chunk(0, 0).id != _surface_chunk(1, 0).id


class TestDistributionSanity:
    def test_region_has_variety_and_some_water(self):
        f = WorldFields(SEED)
        from app.engine.biomes import classify, is_water
        seen = set()
        water = total = 0
        for gx in range(0, 1024, 8):
            for gy in range(0, 1024, 8):
                h = f.height(gx, gy)
                seen.add(classify(h, f.moisture(gx, gy), f.heat(gx, gy)))
                water += 1 if is_water(h) else 0
                total += 1
        assert len(seen) >= 3
        assert 0.02 < water / total < 0.85


class TestNonSurfaceLayers:
    def test_sky_biomes_minimal(self):
        chunk = generate_chunk(WID, SEED, Layer.SKY, 0, 0)
        assert chunk.biome in {"void", "floating_island"}
        for cell in chunk.terrain_cells:
            assert cell["biome"] in {"void", "floating_island"}

    def test_underground_biomes_minimal(self):
        chunk = generate_chunk(WID, SEED, Layer.UNDERGROUND, 0, 0)
        assert chunk.biome in {"rock", "cavern"}

    def test_ocean_layer_biomes_minimal(self):
        chunk = generate_chunk(WID, SEED, Layer.OCEAN, 0, 0)
        assert chunk.biome in {"deep_water", "trench"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_chunk_manager.py -v`
Expected: FAIL — the current `chunk_manager.py` produces cells without `heat`/`water` and a hardcoded biome, so `test_cell_count_and_new_keys`, `test_chunk_biome_is_known`, and the seam tests fail.

- [ ] **Step 3: Rewrite the implementation**

Replace the entire contents of `backend/app/engine/chunk_manager.py` with:

```python
from __future__ import annotations
from collections import Counter
from app.models.schemas import Chunk, Layer
from app.engine.fields import WorldFields
from app.engine.biomes import classify, is_water, is_river

CHUNK_SIZE = 64


def _chunk_id(world_id: str, layer: Layer, cx: int, cy: int) -> str:
    return f"{world_id}:{layer.value}:{cx}:{cy}"


def _surface_cell(fields: WorldFields, gx: int, gy: int) -> dict:
    h = fields.height(gx, gy)
    m = fields.moisture(gx, gy)
    t = fields.heat(gx, gy)
    flow = fields.flow(gx, gy)
    water = is_water(h)
    river = (not water) and is_river(flow, h)
    biome = "river" if river else classify(h, m, t)
    return {
        "x": gx, "y": gy,
        "elevation": h, "moisture": m, "heat": t,
        "biome": biome, "water": water or river,
    }


def _nonsurface_cell(layer: Layer, fields: WorldFields, gx: int, gy: int) -> dict:
    """Minimal coherent fields for non-surface layers (one channel -> two biomes)."""
    h = fields.height(gx, gy)
    if layer == Layer.SKY:
        biome, water = ("floating_island" if h >= 0.62 else "void"), False
    elif layer == Layer.OCEAN:
        biome, water = ("trench" if h < 0.30 else "deep_water"), True
    else:  # UNDERGROUND, DEEP
        biome, water = ("cavern" if h >= 0.55 else "rock"), False
    return {"x": gx, "y": gy, "elevation": h, "moisture": 0.0, "heat": 0.0,
            "biome": biome, "water": water}


def generate_chunk(world_id: str, seed: int, layer: Layer, cx: int, cy: int) -> Chunk:
    fields = WorldFields(seed)
    is_surface = layer == Layer.SURFACE

    cells: list[dict] = []
    for y in range(CHUNK_SIZE):
        for x in range(CHUNK_SIZE):
            gx = cx * CHUNK_SIZE + x
            gy = cy * CHUNK_SIZE + y
            cells.append(
                _surface_cell(fields, gx, gy) if is_surface
                else _nonsurface_cell(layer, fields, gx, gy)
            )

    modal_biome = Counter(c["biome"] for c in cells).most_common(1)[0][0]

    center_gx = cx * CHUNK_SIZE + CHUNK_SIZE // 2
    center_gy = cy * CHUNK_SIZE + CHUNK_SIZE // 2

    return Chunk(
        id=_chunk_id(world_id, layer, cx, cy),
        world_id=world_id,
        layer=layer,
        chunk_x=cx,
        chunk_y=cy,
        biome=modal_biome,
        terrain_cells=cells,
        structures=[],
        entities=[],
        danger_level=fields.danger(center_gx, center_gy),
        power_influence=fields.power(center_gx, center_gy),
    )
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chunk_manager.py -v`
Expected: PASS.

- [ ] **Step 5: Run the existing generation suite to verify no regression**

Run: `cd backend && python -m pytest tests/test_generation.py -v`
Expected: PASS — every existing assertion (incl. `test_same_seed_same_chunk`, `test_chunk_different_positions_differ`) still holds; `generate_world` is untouched.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS — the whole suite (Stage-1 AI tests + new engine tests) is green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/engine/chunk_manager.py backend/tests/test_chunk_manager.py
git commit -m "feat(engine): seamless noise-driven chunk generation (stage2 #1)"
```

---

## Notes for the implementer

- **Run everything from `backend/`** (`cd backend && python -m pytest ...`); the tests import `from app...`.
- **If `test_region_has_variety_and_some_water` ever fails** on a future tuning change, the cause is almost always the `SEA_LEVEL`/biome thresholds or fBm normalization, not the test — adjust the constants in `biomes.py`, do not loosen the test below the stated sanity band.
- **Do not add a `Chunk` schema field.** If you think you need one, you don't for #1 — per-cell power and ocean/lake distinction are explicitly deferred (spec §13).
