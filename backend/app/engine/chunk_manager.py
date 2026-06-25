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
