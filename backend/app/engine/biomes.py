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
