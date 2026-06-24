from __future__ import annotations
import sqlite3
import os
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent.parent / "aetherworld.db"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    # Resolve DB_PATH at call time (not as a default arg) so tests can redirect
    # the database to a temp file via monkeypatch without touching the real DB.
    conn = sqlite3.connect(str(db_path if db_path is not None else DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS worlds (
                id TEXT PRIMARY KEY,
                seed INTEGER NOT NULL,
                name TEXT NOT NULL,
                base_generated_version TEXT NOT NULL DEFAULT '0.1.0',
                current_tick INTEGER NOT NULL DEFAULT 0,
                regions TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                world_id TEXT NOT NULL,
                layer TEXT NOT NULL,
                chunk_x INTEGER NOT NULL,
                chunk_y INTEGER NOT NULL,
                biome TEXT NOT NULL DEFAULT 'plains',
                terrain_cells TEXT NOT NULL DEFAULT '[]',
                structures TEXT NOT NULL DEFAULT '[]',
                entities TEXT NOT NULL DEFAULT '[]',
                danger_level REAL NOT NULL DEFAULT 0.0,
                power_influence TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (world_id) REFERENCES worlds(id)
            );

            CREATE TABLE IF NOT EXISTS structures (
                id TEXT PRIMARY KEY,
                world_id TEXT NOT NULL,
                type TEXT NOT NULL,
                layer TEXT NOT NULL,
                position TEXT NOT NULL DEFAULT '{}',
                footprint TEXT NOT NULL DEFAULT '{}',
                influence_zone TEXT NOT NULL DEFAULT '{}',
                exclusion_zone TEXT NOT NULL DEFAULT '{}',
                entrances TEXT NOT NULL DEFAULT '[]',
                owner_faction_id TEXT,
                power_influence TEXT NOT NULL DEFAULT '{}',
                story_hooks TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (world_id) REFERENCES worlds(id)
            );

            CREATE TABLE IF NOT EXISTS entrance_contracts (
                id TEXT PRIMARY KEY,
                source_layer TEXT NOT NULL,
                source_position TEXT NOT NULL DEFAULT '{}',
                target_layer TEXT NOT NULL,
                target_position TEXT NOT NULL DEFAULT '{}',
                access_type TEXT NOT NULL DEFAULT 'open',
                is_returnable INTEGER NOT NULL DEFAULT 1,
                locked_by TEXT
            );

            CREATE TABLE IF NOT EXISTS factions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                principle_bias TEXT NOT NULL DEFAULT '[]',
                home_structure_id TEXT,
                goals TEXT NOT NULL DEFAULT '[]',
                relationships TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS npcs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                faction_id TEXT,
                location_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'villager',
                personality_tags TEXT NOT NULL DEFAULT '[]',
                known_facts TEXT NOT NULL DEFAULT '[]',
                secrets TEXT NOT NULL DEFAULT '[]',
                power_profile TEXT NOT NULL DEFAULT '{}',
                alive INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS ai_proposals (
                id TEXT PRIMARY KEY,
                proposal_type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'ai',
                referenced_world_ids TEXT NOT NULL DEFAULT '[]',
                payload TEXT NOT NULL DEFAULT '{}',
                validation_status TEXT NOT NULL DEFAULT 'pending',
                rejection_reasons TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS storyboard_cards (
                id TEXT PRIMARY KEY,
                scene_title TEXT NOT NULL,
                location_id TEXT NOT NULL,
                characters_present TEXT NOT NULL DEFAULT '[]',
                visual_focus TEXT NOT NULL DEFAULT '',
                mood TEXT NOT NULL DEFAULT '',
                gameplay_objective TEXT NOT NULL DEFAULT '',
                revealed_information TEXT NOT NULL DEFAULT '[]',
                validation_requirements TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS story_arcs (
                id TEXT PRIMARY KEY,
                world_id TEXT NOT NULL,
                title TEXT NOT NULL,
                premise TEXT NOT NULL DEFAULT '',
                theme TEXT NOT NULL DEFAULT '',
                beats TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS story_beats (
                id TEXT PRIMARY KEY,
                arc_id TEXT NOT NULL,
                act INTEGER NOT NULL DEFAULT 1,
                "order" INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL DEFAULT '',
                location_ids TEXT NOT NULL DEFAULT '[]',
                character_ids TEXT NOT NULL DEFAULT '[]',
                faction_ids TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft'
            );

            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                beat_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                prose TEXT NOT NULL DEFAULT '',
                dialogue TEXT NOT NULL DEFAULT '[]',
                storyboard_card_id TEXT,
                revealed_information TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft'
            );

            CREATE TABLE IF NOT EXISTS bible_entries (
                id TEXT PRIMARY KEY,
                world_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                ref_id TEXT NOT NULL,
                text TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS bible_vectors (
                entry_id TEXT PRIMARY KEY,
                dim INTEGER NOT NULL,
                vector TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()
