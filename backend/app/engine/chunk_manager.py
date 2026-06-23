from __future__ import annotations
import hashlib
import json
import random
from app.models.schemas import Chunk, Layer


CHUNK_SIZE = 64
RIVERFALL_CHUNKS = {
    (0, 0): "plains",
    (0, 1): "plains",
    (1, 0): "plains",
    (1, 1): "lake",
    (2, 0): "forest",
    (2, 1): "plains",
    (0, -1): "plains",
    (1, -1): "hills",
    (-1, 0): "plains",
    (-1, 1): "forest",
}


def _chunk_id(world_id: str, layer: Layer, cx: int, cy: int) -> str:
    return f"{world_id}:{layer.value}:{cx}:{cy}"


def _biome_from_position(cx: int, cy: int) -> str:
    key = (cx, cy)
    return RIVERFALL_CHUNKS.get(key, "plains")


def _generate_terrain_cells(seed: int, cx: int, cy: int, layer: Layer, biome: str) -> list[dict]:
    h = hashlib.sha256(f"{seed}:{cx}:{cy}:{layer.value}:terrain".encode()).hexdigest()
    cell_seed = int(h[:16], 16)
    rng = random.Random(cell_seed)

    cells = []
    for y in range(CHUNK_SIZE):
        for x in range(CHUNK_SIZE):
            world_x = cx * CHUNK_SIZE + x
            world_y = cy * CHUNK_SIZE + y
            elevation = rng.random()
            moisture = rng.random()
            cell = {
                "x": world_x,
                "y": world_y,
                "elevation": round(elevation, 4),
                "moisture": round(moisture, 4),
                "biome": biome,
            }
            cells.append(cell)

    return cells


def _generate_power_influence(seed: int, cx: int, cy: int, layer: Layer) -> dict[str, float]:
    h = hashlib.sha256(f"{seed}:{cx}:{cy}:{layer.value}:power".encode()).hexdigest()
    rng = random.Random(int(h[:16], 16))

    return {
        "magic": round(rng.random(), 4),
        "aura": round(rng.random(), 4),
        "alchemy": round(rng.random(), 4),
        "mechanical": round(rng.random(), 4),
        "biological": round(rng.random(), 4),
        "mind": round(rng.random(), 4),
    }


def _generate_danger(seed: int, cx: int, cy: int, layer: Layer) -> float:
    h = hashlib.sha256(f"{seed}:{cx}:{cy}:{layer.value}:danger".encode()).hexdigest()
    rng = random.Random(int(h[:16], 16))
    return round(rng.random(), 4)


def generate_chunk(world_id: str, seed: int, layer: Layer, cx: int, cy: int) -> Chunk:
    biome = _biome_from_position(cx, cy)
    terrain_cells = _generate_terrain_cells(seed, cx, cy, layer, biome)
    power_influence = _generate_power_influence(seed, cx, cy, layer)
    danger_level = _generate_danger(seed, cx, cy, layer)

    return Chunk(
        id=_chunk_id(world_id, layer, cx, cy),
        world_id=world_id,
        layer=layer,
        chunk_x=cx,
        chunk_y=cy,
        biome=biome,
        terrain_cells=terrain_cells,
        structures=[],
        entities=[],
        danger_level=danger_level,
        power_influence=power_influence,
    )
