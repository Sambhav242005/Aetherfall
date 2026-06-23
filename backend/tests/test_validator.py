import pytest
from app.engine.overlap_validator import validate_structure_placement
from app.engine.world_generator import generate_world


class TestOverlapValidator:
    def test_no_conflict_between_remote_structures(self):
        lake = {
            "id": "lake",
            "type": "lake",
            "layer": "surface",
            "position": {"x": 0, "y": 0},
            "footprint": {"width": 20, "height": 20, "shape": "ellipse"},
            "exclusion_zone": {"width": 20, "height": 20, "shape": "ellipse", "reason": "water"},
        }
        town = {
            "id": "town",
            "type": "town",
            "layer": "surface",
            "position": {"x": 200, "y": 200},
            "footprint": {"width": 30, "height": 30, "shape": "polygon"},
            "exclusion_zone": {"width": 30, "height": 30, "shape": "polygon", "reason": "town_buildings"},
        }
        ok, reasons = validate_structure_placement(town, [lake])
        assert ok
        assert len(reasons) == 0

    def test_rejects_farm_in_lake(self):
        lake = {
            "id": "lake",
            "type": "lake",
            "layer": "surface",
            "position": {"x": 0, "y": 0},
            "footprint": {"width": 100, "height": 100, "shape": "ellipse"},
            "exclusion_zone": {"width": 100, "height": 100, "shape": "ellipse", "reason": "water"},
        }
        farm = {
            "id": "farm",
            "type": "farmland",
            "layer": "surface",
            "position": {"x": 10, "y": 10},
            "footprint": {"width": 40, "height": 40, "shape": "polygon"},
            "exclusion_zone": {"width": 5, "height": 5, "shape": "none", "reason": ""},
        }
        ok, reasons = validate_structure_placement(farm, [lake])
        assert not ok
        assert any("farmland" in r and "water" in r for r in reasons)

    def test_rejects_town_in_lake(self):
        lake = {
            "id": "lake",
            "type": "lake",
            "layer": "surface",
            "position": {"x": 0, "y": 0},
            "footprint": {"width": 100, "height": 100, "shape": "ellipse"},
            "exclusion_zone": {"width": 100, "height": 100, "shape": "ellipse", "reason": "water"},
        }
        town = {
            "id": "town",
            "type": "town",
            "layer": "surface",
            "position": {"x": 0, "y": 0},
            "footprint": {"width": 30, "height": 30, "shape": "polygon"},
            "exclusion_zone": {"width": 30, "height": 30, "shape": "polygon", "reason": "town_buildings"},
        }
        ok, reasons = validate_structure_placement(town, [lake])
        assert not ok

    def test_rejects_cave_blocked_by_castle(self):
        castle = {
            "id": "castle",
            "type": "castle",
            "layer": "surface",
            "position": {"x": 0, "y": 0},
            "footprint": {"width": 60, "height": 60, "shape": "polygon"},
            "exclusion_zone": {"width": 60, "height": 60, "shape": "polygon", "reason": "castle_grounds"},
        }
        cave = {
            "id": "cave",
            "type": "cave_entrance",
            "layer": "surface",
            "position": {"x": 10, "y": 10},
            "footprint": {"width": 16, "height": 16, "shape": "circle"},
            "exclusion_zone": {"width": 16, "height": 16, "shape": "circle", "reason": "cave_mouth"},
        }
        ok, reasons = validate_structure_placement(cave, [castle])
        assert not ok

    def test_different_layers_no_conflict(self):
        lake = {
            "id": "lake",
            "type": "lake",
            "layer": "surface",
            "position": {"x": 0, "y": 0},
            "footprint": {"width": 100, "height": 100, "shape": "ellipse"},
            "exclusion_zone": {"width": 100, "height": 100, "shape": "ellipse", "reason": "water"},
        }
        underground_dungeon = {
            "id": "dungeon",
            "type": "dungeon",
            "layer": "underground",
            "position": {"x": 0, "y": 0},
            "footprint": {"width": 60, "height": 60, "shape": "polygon"},
            "exclusion_zone": {"width": 60, "height": 60, "shape": "polygon", "reason": "dungeon_walls"},
        }
        ok, reasons = validate_structure_placement(underground_dungeon, [lake])
        assert ok
        assert len(reasons) == 0

    def test_generated_world_validates(self):
        world = generate_world(42)
        assert "structures" in world
        assert "factions" in world
        assert "npcs" in world
