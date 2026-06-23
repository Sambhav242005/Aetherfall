from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Layer(str, Enum):
    SKY = "sky"
    SURFACE = "surface"
    UNDERGROUND = "underground"
    DEEP = "deep"
    OCEAN = "ocean"


class AccessType(str, Enum):
    OPEN = "open"
    LOCKED = "locked"
    SEALED = "sealed"
    SECRET = "secret"


class ValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class World(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    seed: int
    name: str
    base_generated_version: str = "0.1.0"
    current_tick: int = 0
    regions: list[str] = ["Riverfall Valley"]


class Chunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    world_id: str
    layer: Layer
    chunk_x: int
    chunk_y: int
    biome: str
    terrain_cells: list[dict[str, Any]] = Field(default_factory=list)
    structures: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    danger_level: float = 0.0
    power_influence: dict[str, float] = Field(default_factory=dict)


class Structure(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    world_id: str
    type: str
    layer: Layer
    position: dict[str, Any]
    footprint: dict[str, Any]
    influence_zone: dict[str, Any]
    exclusion_zone: dict[str, Any]
    entrances: list[str] = Field(default_factory=list)
    owner_faction_id: str | None = None
    power_influence: dict[str, float] = Field(default_factory=dict)
    story_hooks: list[str] = Field(default_factory=list)


class EntranceContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_layer: Layer
    source_position: dict[str, float]
    target_layer: Layer
    target_position: dict[str, float]
    access_type: AccessType = AccessType.OPEN
    is_returnable: bool = True
    locked_by: str | None = None


class Faction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    principle_bias: list[str] = Field(default_factory=list)
    home_structure_id: str | None = None
    goals: list[str] = Field(default_factory=list)
    relationships: dict[str, int] = Field(default_factory=dict)


class NPC(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    faction_id: str | None = None
    location_id: str
    role: str
    personality_tags: list[str] = Field(default_factory=list)
    known_facts: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    power_profile: dict[str, float] = Field(default_factory=dict)
    alive: bool = True


class AIProposal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    proposal_type: str
    source: str = "ai"
    referenced_world_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    validation_status: ValidationStatus = ValidationStatus.PENDING
    rejection_reasons: list[str] = Field(default_factory=list)


class StoryboardCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scene_title: str
    location_id: str
    characters_present: list[str] = Field(default_factory=list)
    visual_focus: str = ""
    mood: str = ""
    gameplay_objective: str = ""
    revealed_information: list[str] = Field(default_factory=list)
    validation_requirements: list[str] = Field(default_factory=list)
