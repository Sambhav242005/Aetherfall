from app.engine.chunk_manager import generate_chunk, CHUNK_SIZE
from app.engine.fields import WorldFields, POWER_PRINCIPLES
from app.engine.biomes import BIOMES, classify, is_water
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
