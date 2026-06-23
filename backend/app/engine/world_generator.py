from __future__ import annotations
import hashlib
import random
import uuid
from app.models.schemas import (
    World, Chunk, Structure, EntranceContract, Faction, NPC, Layer, AccessType,
)
from app.engine.chunk_manager import generate_chunk
from app.engine.overlap_validator import validate_world


SEED_PHRASE = "Riverfall Valley MVP v0.1.0"


def _derive_seed(base_seed: int, salt: str) -> int:
    h = hashlib.sha256(f"{base_seed}:{salt}".encode()).hexdigest()
    return int(h[:16], 16)


def _pick(items: list, rng: random.Random) -> str:
    return rng.choice(items)


def generate_world(seed: int | None = None) -> dict:
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    rng = random.Random(seed)
    world_id = str(uuid.uuid4())

    world = World(
        id=world_id,
        seed=seed,
        name="Riverfall Valley",
    )

    structures, entrances, factions, npcs = _generate_riverfall_valley(world_id, rng)

    world_data = {
        "world": world.model_dump(mode="json"),
        "structures": [s.model_dump(mode="json") for s in structures],
        "entrance_contracts": [e.model_dump(mode="json") for e in entrances],
        "factions": [f.model_dump(mode="json") for f in factions],
        "npcs": [n.model_dump(mode="json") for n in npcs],
    }

    validate_world(world_data)

    return world_data


def _generate_riverfall_valley(world_id: str, rng: random.Random):
    structures: list[Structure] = []
    entrances: list[EntranceContract] = []
    factions: list[Faction] = []
    npcs: list[NPC] = []

    faction_guild_id = "faction_alchemy_guild"
    faction_lord_id = "faction_castle_lord"
    faction_farmers_id = "faction_riverfall_farmers"

    factions = [
        Faction(
            id=faction_guild_id,
            name="Alchemy Guild of Riverfall",
            principle_bias=["alchemy", "magic"],
            home_structure_id=None,
            goals=["harvest moonlake crystals", "study floating island magic"],
            relationships={faction_lord_id: -2, faction_farmers_id: -1},
        ),
        Faction(
            id=faction_lord_id,
            name="Castle Lord's Garrison",
            principle_bias=["mechanical", "aura"],
            home_structure_id="struct_old_stone_castle",
            goals=["contain the lake mutation", "hide alchemy experiment"],
            relationships={faction_guild_id: -2, faction_farmers_id: 1},
        ),
        Faction(
            id=faction_farmers_id,
            name="Riverfall Farming Collective",
            principle_bias=["biological", "alchemy"],
            home_structure_id=None,
            goals=["stop crop sickness", "find clean water"],
            relationships={faction_guild_id: -1, faction_lord_id: 1},
        ),
    ]

    moonlake_center = {"x": 500.0, "y": 400.0}
    town_center = {"x": 300.0, "y": 500.0}
    castle_center = {"x": 600.0, "y": 300.0}
    forest_center = {"x": 200.0, "y": 200.0}
    cave_entrance_pos = {"x": 550.0, "y": 450.0}
    floating_island_pos = {"x": 500.0, "y": 100.0}
    farm_center = {"x": 350.0, "y": 550.0}

    structures = [
        Structure(
            id="struct_moonlake",
            world_id=world_id,
            type="lake",
            layer=Layer.SURFACE,
            position=moonlake_center,
            footprint={"width": 160.0, "height": 120.0, "shape": "ellipse"},
            influence_zone={"radius": 100.0, "effects": ["magic_contamination", "mutation"]},
            exclusion_zone={"width": 160.0, "height": 120.0, "shape": "ellipse", "reason": "water"},
            owner_faction_id=None,
            power_influence={"magic": 0.6, "alchemy": 0.4},
            story_hooks=["lake mutation", "dead fish", "glowing water"],
        ),
        Structure(
            id="struct_riverfall_town",
            world_id=world_id,
            type="town",
            layer=Layer.SURFACE,
            position=town_center,
            footprint={"width": 100.0, "height": 80.0, "shape": "polygon"},
            influence_zone={"radius": 80.0, "effects": ["civilization", "trade"]},
            exclusion_zone={"width": 100.0, "height": 80.0, "shape": "polygon", "reason": "town_buildings"},
            owner_faction_id=faction_farmers_id,
            power_influence={"biological": 0.3},
            story_hooks=["sick farmers", "market gossip"],
        ),
        Structure(
            id="struct_old_stone_castle",
            world_id=world_id,
            type="castle",
            layer=Layer.SURFACE,
            position=castle_center,
            footprint={"width": 90.0, "height": 70.0, "shape": "polygon"},
            influence_zone={"radius": 120.0, "effects": ["authority", "military"]},
            exclusion_zone={"width": 100.0, "height": 80.0, "shape": "polygon", "reason": "castle_grounds"},
            owner_faction_id=faction_lord_id,
            power_influence={"mechanical": 0.5, "aura": 0.4},
            story_hooks=["secret alchemy lab", "old castle drain"],
        ),
        Structure(
            id="struct_northwood_forest",
            world_id=world_id,
            type="forest",
            layer=Layer.SURFACE,
            position=forest_center,
            footprint={"width": 180.0, "height": 150.0, "shape": "polygon"},
            influence_zone={"radius": 50.0, "effects": ["woodland", "hunting"]},
            exclusion_zone={"width": 10.0, "height": 10.0, "shape": "none", "reason": ""},
            owner_faction_id=None,
            power_influence={"biological": 0.6},
            story_hooks=["old hunting grounds", "hidden grove"],
        ),
        Structure(
            id="struct_cave_entrance",
            world_id=world_id,
            type="cave_entrance",
            layer=Layer.SURFACE,
            position=cave_entrance_pos,
            footprint={"width": 16.0, "height": 16.0, "shape": "circle"},
            influence_zone={"radius": 20.0, "effects": ["danger", "mystery"]},
            exclusion_zone={"width": 16.0, "height": 16.0, "shape": "circle", "reason": "cave_mouth"},
            owner_faction_id=None,
            power_influence={"alchemy": 0.3},
            story_hooks=["dark tunnel", "strange sounds"],
        ),
        Structure(
            id="struct_floating_island",
            world_id=world_id,
            type="floating_island",
            layer=Layer.SKY,
            position=floating_island_pos,
            footprint={"width": 60.0, "height": 40.0, "shape": "ellipse"},
            influence_zone={"radius": 80.0, "effects": ["magic_leak", "sky_shadow"]},
            exclusion_zone={"width": 60.0, "height": 40.0, "shape": "ellipse", "reason": "island_base"},
            owner_faction_id=None,
            power_influence={"magic": 0.9},
            story_hooks=["magic leak into lake", "ancient shrine"],
        ),
        Structure(
            id="struct_farms",
            world_id=world_id,
            type="farmland",
            layer=Layer.SURFACE,
            position=farm_center,
            footprint={"width": 120.0, "height": 80.0, "shape": "polygon"},
            influence_zone={"radius": 40.0, "effects": ["agriculture", "sickness"]},
            exclusion_zone={"width": 5.0, "height": 5.0, "shape": "none", "reason": ""},
            owner_faction_id=faction_farmers_id,
            power_influence={"biological": 0.4},
            story_hooks=["mutating crops", "sick livestock"],
        ),
        Structure(
            id="struct_broken_bridge",
            world_id=world_id,
            type="bridge_ruin",
            layer=Layer.SURFACE,
            position={"x": 450.0, "y": 380.0},
            footprint={"width": 30.0, "height": 10.0, "shape": "rectangle"},
            influence_zone={"radius": 10.0, "effects": ["obstacle"]},
            exclusion_zone={"width": 30.0, "height": 10.0, "shape": "rectangle", "reason": "ruin"},
            owner_faction_id=None,
            power_influence={},
            story_hooks=["broken trade route", "lost cargo"],
        ),
        Structure(
            id="struct_abandoned_alchemy_dungeon",
            world_id=world_id,
            type="dungeon",
            layer=Layer.UNDERGROUND,
            position={"x": 580.0, "y": 320.0},
            footprint={"width": 80.0, "height": 60.0, "shape": "polygon"},
            influence_zone={"radius": 30.0, "effects": ["alchemy_danger", "experiment"]},
            exclusion_zone={"width": 80.0, "height": 60.0, "shape": "polygon", "reason": "dungeon_walls"},
            owner_faction_id=faction_lord_id,
            power_influence={"alchemy": 0.8, "mechanical": 0.3},
            story_hooks=["lord's secret experiment", "alchemy gone wrong"],
        ),
        Structure(
            id="struct_crystal_cave",
            world_id=world_id,
            type="dungeon",
            layer=Layer.UNDERGROUND,
            position={"x": 500.0, "y": 420.0},
            footprint={"width": 70.0, "height": 50.0, "shape": "polygon"},
            influence_zone={"radius": 25.0, "effects": ["crystal_growth", "magic_echo"]},
            exclusion_zone={"width": 70.0, "height": 50.0, "shape": "polygon", "reason": "cave_walls"},
            owner_faction_id=None,
            power_influence={"magic": 0.7, "alchemy": 0.5},
            story_hooks=["glowing crystals", "guild interest"],
        ),
        Structure(
            id="struct_ancient_magic_shrine",
            world_id=world_id,
            type="shrine",
            layer=Layer.SKY,
            position={"x": 500.0, "y": 80.0},
            footprint={"width": 30.0, "height": 30.0, "shape": "polygon"},
            influence_zone={"radius": 40.0, "effects": ["magic_purity", "ancient_power"]},
            exclusion_zone={"width": 30.0, "height": 30.0, "shape": "polygon", "reason": "shrine"},
            owner_faction_id=None,
            power_influence={"magic": 1.0, "mind": 0.3},
            story_hooks=["ancient magic source", "shrine riddle"],
        ),
    ]

    entrances = [
        EntranceContract(
            id="entrance_cave_to_dungeon",
            source_layer=Layer.SURFACE,
            source_position=cave_entrance_pos,
            target_layer=Layer.UNDERGROUND,
            target_position={"x": 580.0, "y": 320.0},
            access_type=AccessType.OPEN,
            is_returnable=True,
        ),
        EntranceContract(
            id="entrance_cave_to_crystal",
            source_layer=Layer.SURFACE,
            source_position=cave_entrance_pos,
            target_layer=Layer.UNDERGROUND,
            target_position={"x": 500.0, "y": 420.0},
            access_type=AccessType.OPEN,
            is_returnable=True,
        ),
        EntranceContract(
            id="entrance_dungeon_return",
            source_layer=Layer.UNDERGROUND,
            source_position={"x": 580.0, "y": 320.0},
            target_layer=Layer.SURFACE,
            target_position=cave_entrance_pos,
            access_type=AccessType.OPEN,
            is_returnable=True,
        ),
        EntranceContract(
            id="entrance_crystal_return",
            source_layer=Layer.UNDERGROUND,
            source_position={"x": 500.0, "y": 420.0},
            target_layer=Layer.SURFACE,
            target_position=cave_entrance_pos,
            access_type=AccessType.OPEN,
            is_returnable=True,
        ),
        EntranceContract(
            id="entrance_shrine_island",
            source_layer=Layer.SKY,
            source_position=floating_island_pos,
            target_layer=Layer.SKY,
            target_position={"x": 500.0, "y": 80.0},
            access_type=AccessType.OPEN,
            is_returnable=True,
        ),
    ]

    npcs = [
        NPC(id="npc_001", name="Elara", faction_id=faction_farmers_id, location_id="struct_riverfall_town",
            role="farmer", personality_tags=["worried", "hardworking"], known_facts=["crops are failing", "lake tastes strange"],
            secrets=["saw someone drain the old castle pipe at night"], power_profile={"biological": 0.2}),
        NPC(id="npc_002", name="Bram", faction_id=faction_farmers_id, location_id="struct_farms",
            role="herder", personality_tags=["quiet", "observant"], known_facts=["livestock is sick", "well water glows"],
            secrets=["found a strange crystal shard near the lake"], power_profile={"biological": 0.2}),
        NPC(id="npc_003", name="Captain Voss", faction_id=faction_lord_id, location_id="struct_old_stone_castle",
            role="captain of the guard", personality_tags=["stern", "loyal"], known_facts=["lord is hiding something", "castle basement is off-limits"],
            secrets=["knows about the alchemy lab"], power_profile={"aura": 0.4, "mechanical": 0.2}),
        NPC(id="npc_004", name="Lord Aldric", faction_id=faction_lord_id, location_id="struct_old_stone_castle",
            role="castle lord", personality_tags=["secretive", "anxious"], known_facts=["alchemy experiment failed", "lake mutation is my fault"],
            secrets=["opened the old drain to hide evidence"], power_profile={"mechanical": 0.5, "alchemy": 0.3}),
        NPC(id="npc_005", name="Mira", faction_id=faction_guild_id, location_id="struct_riverfall_town",
            role="alchemist", personality_tags=["curious", "ambitious"], known_facts=["crystals in moonlake are valuable", "floating island leaks magic"],
            secrets=["wants to harvest the crystals before the lord stops her"], power_profile={"alchemy": 0.6, "magic": 0.3}),
        NPC(id="npc_006", name="Kael", faction_id=faction_guild_id, location_id="struct_riverfall_town",
            role="apprentice", personality_tags=["eager", "nervous"], known_facts=["guild wants moonlake crystals", "Mira is planning something"],
            secrets=["overheard a plan to poison the lord's well"], power_profile={"alchemy": 0.2}),
        NPC(id="npc_007", name="Old Tessa", faction_id=faction_farmers_id, location_id="struct_riverfall_town",
            role="herbalist", personality_tags=["wise", "distrustful"], known_facts=["plants change near the lake", "old magic in the valley"],
            secrets=["knows about the ancient shrine on the floating island"], power_profile={"biological": 0.5, "magic": 0.2}),
        NPC(id="npc_008", name="Finn", faction_id=None, location_id="struct_northwood_forest",
            role="hunter", personality_tags=["independent", "suspicious"], known_facts=["animals avoid the lake", "strange lights in the forest"],
            secrets=["found a hidden tunnel near the old bridge"], power_profile={"biological": 0.3, "aura": 0.2}),
        NPC(id="npc_009", name="Serra", faction_id=faction_lord_id, location_id="struct_old_stone_castle",
            role="castle scholar", personality_tags=["bookish", "curious"], known_facts=["old records mention floating island", "castle was built on older ruins"],
            secrets=["deciphered part of the ancient shrine script"], power_profile={"mind": 0.4}),
        NPC(id="npc_010", name="Doran", faction_id=None, location_id="struct_riverfall_town",
            role="innkeeper", personality_tags=["friendly", "nosy"], known_facts=["everyone's business", "travelers have stopped coming"],
            secrets=["overheard the alchemy guild planning something"], power_profile={}),
        NPC(id="npc_011", name="Lena", faction_id=faction_farmers_id, location_id="struct_farms",
            role="farmer", personality_tags=["tired", "hopeful"], known_facts=["children are getting sick", "river water is discolored"],
            secrets=["has a sample of glowing water hidden away"], power_profile={"biological": 0.1}),
        NPC(id="npc_012", name="Garen", faction_id=faction_lord_id, location_id="struct_old_stone_castle",
            role="guard", personality_tags=["dutiful", "superstitious"], known_facts=["basement door is always locked", "lord seems scared"],
            secrets=["once heard screaming from the basement"], power_profile={"aura": 0.3}),
        NPC(id="npc_013", name="Sylvie", faction_id=faction_guild_id, location_id="struct_riverfall_town",
            role="merchant", personality_tags=["shrewd", "charming"], known_facts=["crystal prices are rising", "guild pays well for rare ingredients"],
            secrets=["sells information to both the guild and the castle"], power_profile={"alchemy": 0.1}),
        NPC(id="npc_014", name="Brother Orin", faction_id=None, location_id="struct_riverfall_town",
            role="healer", personality_tags=["compassionate", "overwhelmed"], known_facts=["sickness is not natural", "standard remedies fail"],
            secrets=["suspects magical contamination"], power_profile={"biological": 0.3, "mind": 0.2}),
        NPC(id="npc_015", name="Rin", faction_id=None, location_id="struct_northwood_forest",
            role="wanderer", personality_tags=["mysterious", "knowledgeable"], known_facts=["valley has ancient power sources", "six principles shape the land"],
            secrets=["is searching for the ancient shrine"], power_profile={"magic": 0.4, "mind": 0.3}),
        NPC(id="npc_016", name="Heston", faction_id=faction_farmers_id, location_id="struct_farms",
            role="farmer", personality_tags=["angry", "desperate"], known_facts=["crops are all dying", "livestock is dying too"],
            secrets=["plans to burn the castle down"], power_profile={"biological": 0.2}),
        NPC(id="npc_017", name="Vesper", faction_id=faction_guild_id, location_id="struct_riverfall_town",
            role="guild envoy", personality_tags=["polished", "calculating"], known_facts=["guild has backing from the capital", "crystals could fund a revolution"],
            secrets=["carries a sealed letter from the capital"], power_profile={"mind": 0.3, "alchemy": 0.2}),
        NPC(id="npc_018", name="Torvin", faction_id=None, location_id="struct_cave_entrance",
            role="prospector", personality_tags=["greedy", "reckless"], known_facts=["crystals deeper in the cave", "something lives in the dark"],
            secrets=["found a vein of pure magical crystal"], power_profile={"mechanical": 0.2}),
        NPC(id="npc_019", name="Iris", faction_id=None, location_id="struct_broken_bridge",
            role="traveler", personality_tags=["lost", "frightened"], known_facts=["bridge has been broken for weeks", "river is hard to cross"],
            secrets=["carries a map of old tunnels under the valley"], power_profile={}),
        NPC(id="npc_020", name="Warden Stone", faction_id=faction_lord_id, location_id="struct_old_stone_castle",
            role="dungeon warden", personality_tags=["silent", "intimidating"], known_facts=["prisoner in the basement", "lord's experiment"],
            secrets=["the prisoner is not human anymore"], power_profile={"aura": 0.5, "mechanical": 0.3}),
    ]

    return structures, entrances, factions, npcs
