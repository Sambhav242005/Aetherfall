from app.engine.world_generator import generate_world
from app.engine.chunk_manager import generate_chunk
from app.models.schemas import Layer


class TestDeterministicGeneration:
    def test_same_seed_produces_same_world(self):
        seed = 12345
        world_a = generate_world(seed)
        world_b = generate_world(seed)

        assert world_a["world"]["seed"] == world_b["world"]["seed"]
        assert world_a["world"]["name"] == world_b["world"]["name"]

        assert len(world_a["structures"]) == len(world_b["structures"])
        assert len(world_a["npcs"]) == len(world_b["npcs"])
        assert len(world_a["factions"]) == len(world_b["factions"])

        for a, b in zip(world_a["structures"], world_b["structures"]):
            assert a["id"] == b["id"]
            assert a["type"] == b["type"]
            assert a["layer"] == b["layer"]

        for a, b in zip(world_a["factions"], world_b["factions"]):
            assert a["id"] == b["id"]
            assert a["name"] == b["name"]

        for a, b in zip(world_a["npcs"], world_b["npcs"]):
            assert a["id"] == b["id"]
            assert a["name"] == b["name"]

    def test_different_seeds_different_world_ids(self):
        world_a = generate_world(42)
        world_b = generate_world(99)

        assert world_a["world"]["id"] != world_b["world"]["id"]

    def test_same_seed_same_chunk(self):
        seed = 42
        world = generate_world(seed)
        world_id = world["world"]["id"]

        chunk_a = generate_chunk(world_id, seed, Layer.SURFACE, 0, 0)
        chunk_b = generate_chunk(world_id, seed, Layer.SURFACE, 0, 0)

        assert chunk_a.id == chunk_b.id
        assert chunk_a.biome == chunk_b.biome

        cells_a = chunk_a.terrain_cells
        cells_b = chunk_b.terrain_cells
        assert len(cells_a) == len(cells_b)
        for ca, cb in zip(cells_a, cells_b):
            assert ca["elevation"] == cb["elevation"]
            assert ca["moisture"] == cb["moisture"]

    def test_chunk_different_positions_differ(self):
        seed = 42
        world = generate_world(seed)
        world_id = world["world"]["id"]

        chunk_00 = generate_chunk(world_id, seed, Layer.SURFACE, 0, 0)
        chunk_01 = generate_chunk(world_id, seed, Layer.SURFACE, 0, 1)
        chunk_10 = generate_chunk(world_id, seed, Layer.SURFACE, 1, 0)

        assert chunk_00.id != chunk_01.id
        assert chunk_00.id != chunk_10.id

    def test_world_has_required_structures(self):
        seed = 999
        world = generate_world(seed)
        types = {s["type"] for s in world["structures"]}

        assert "lake" in types
        assert "town" in types
        assert "castle" in types
        assert "forest" in types
        assert "cave_entrance" in types
        assert "floating_island" in types
        assert "farmland" in types
        assert "bridge_ruin" in types
        assert "dungeon" in types
        assert "shrine" in types

    def test_world_has_three_factions(self):
        world = generate_world(42)
        assert len(world["factions"]) == 3

    def test_world_has_twenty_npcs(self):
        world = generate_world(42)
        assert len(world["npcs"]) == 20

    def test_world_name_is_riverfall_valley(self):
        world = generate_world(42)
        assert world["world"]["name"] == "Riverfall Valley"
