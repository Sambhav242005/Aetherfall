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
