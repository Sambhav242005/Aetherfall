"""AI worldbuilder: drafts a canonical World Bible from the procedural world.

The AI authors it (source='ai', status='draft'); a human reviews/edits via the
API (source='human'). `render_world_bible` turns it into a compact canon block
that the Retriever injects ahead of procedural facts, so story generation is
grounded in a coherent setting instead of improvising one.

A cross-model verifier scores the draft for completeness, internal conflict, and
coherence, then a short repair loop feeds its fix-hints back to the author so no
field (and no layer) is left empty or contradictory.
"""
from __future__ import annotations
import json
import sqlite3
from app.ai.json_utils import extract_json_object
from app.ai.model_router import ModelRouter
from app.models.schemas import VerifierVerdict, WorldBible

_LAYERS = ("sky", "surface", "underground", "deep", "ocean")

_BIBLE_SYSTEM = (
    "You are the lead worldbuilder for a layered fantasy RPG named Aetherfall. "
    "Using the WORLD SEED FACTS as your anchor, write a rich, internally-consistent "
    "world bible. The world is vertically stacked — sky, surface, underground, deep, "
    "ocean — and a raw substance called 'aether' falls from above and accumulates "
    "downward.\n\n"
    "HARD REQUIREMENTS (a draft that breaks any of these will be rejected):\n"
    "1. FILL EVERY FIELD. No field may be empty or a placeholder.\n"
    "2. Describe ALL FIVE layers (sky, surface, underground, deep, ocean) with 2-3 "
    "concrete sentences each. If the seed facts do not mention a layer, INVENT canon "
    "for it that follows from the premise — e.g. the 'deep' is where aether pools and "
    "festers/corrupts, the 'ocean' hides drowned ruins of the world from before THE FALL.\n"
    "3. 'the_fall' MUST be a single CATASTROPHIC PAST EVENT (a moment in history — e.g. "
    "a sky-barrier cracking, a sealed vault breaking) that started the aether falling. "
    "It is NOT ongoing weather and NOT 'rain that keeps falling'. Name what broke and what changed.\n"
    "4. 'aether_system' MUST state a clear COST or DANGER of using/touching aether — "
    "what it does to people, why it is not free power.\n"
    "5. 'factions_overview' MUST name a concrete source of FRICTION or a flashpoint "
    "between factions over aether, territory, or the ruins — not a peaceful coexistence.\n"
    "6. 'history' MUST reference a LOST prior civilization (the builders of the ruins/"
    "shrines/seals) that existed before THE FALL.\n"
    "7. 'peoples' describes living cultures, customs, and beliefs — distinct from the "
    "political 'factions'.\n\n"
    "Reply with ONLY JSON of the form: "
    '{"premise":"","aether_system":"","the_fall":"","history":"",'
    '"layers":{"sky":"","surface":"","underground":"","deep":"","ocean":""},'
    '"peoples":"","factions_overview":"","themes":["",""],"tone":""}. '
    "Do not invent location or faction ids; the qualitative canon above is yours to invent."
)

_BIBLE_VERIFY_SYSTEM = (
    "You are a strict worldbuilding editor for the RPG Aetherfall. Judge the WORLD BIBLE "
    "below on three axes, each scored 0-10:\n"
    "- completeness: every field and ALL FIVE layers (sky, surface, underground, deep, "
    "ocean) are filled with concrete content; empty/placeholder/vague fields score low.\n"
    "- conflict: THE FALL reads as a single past catastrophe (not ongoing weather); "
    "aether has a stated cost/danger; factions have real friction; there is a lost prior "
    "civilization. Missing tension/stakes scores low.\n"
    "- coherence: the layers, aether, history, and factions fit together without "
    "contradiction.\n"
    "Reply with ONLY a JSON object: "
    '{"verdict":"accept|revise|reject","scores":{"completeness":0,"conflict":0,'
    '"coherence":0},"issues":[],"fix_hints":[]}. '
    "Use 'accept' only when every score meets the acceptance threshold; otherwise "
    "'revise' with SPECIFIC fix_hints naming the empty field/layer or the missing tension."
)


def _seed_facts(world_id, conn: sqlite3.Connection) -> str:
    """Flatten the procedural world into seed facts to ground the bible."""
    lines: list[str] = []
    w = conn.execute("SELECT name, seed, regions FROM worlds WHERE id = ?", (world_id,)).fetchone()
    if w is not None:
        try:
            regions = ", ".join(json.loads(w["regions"]))
        except (TypeError, ValueError):
            regions = ""
        lines.append(f"WORLD: {w['name']} (seed {w['seed']}; regions: {regions or 'unknown'})")
    layers = conn.execute(
        "SELECT DISTINCT layer FROM structures WHERE world_id = ? ORDER BY layer", (world_id,)).fetchall()
    if layers:
        lines.append("LAYERS PRESENT: " + ", ".join(r["layer"] for r in layers))
    types = conn.execute(
        "SELECT DISTINCT type FROM structures WHERE world_id = ? ORDER BY type", (world_id,)).fetchall()
    if types:
        lines.append("STRUCTURE TYPES: " + ", ".join(r["type"] for r in types))
    facs = conn.execute("SELECT name FROM factions ORDER BY name").fetchall()
    if facs:
        lines.append("FACTIONS: " + ", ".join(r["name"] for r in facs))
    return "\n".join(lines) or "No procedural facts available."


def load_world_bible(conn: sqlite3.Connection, world_id) -> WorldBible | None:
    row = conn.execute("SELECT * FROM world_bible WHERE world_id = ?", (world_id,)).fetchone()
    if row is None:
        return None
    return WorldBible(
        world_id=row["world_id"], premise=row["premise"], aether_system=row["aether_system"],
        the_fall=row["the_fall"], history=row["history"], layers=json.loads(row["layers"]),
        peoples=row["peoples"], factions_overview=row["factions_overview"],
        themes=json.loads(row["themes"]), tone=row["tone"], status=row["status"], source=row["source"],
    )


def save_world_bible(conn: sqlite3.Connection, bible: WorldBible) -> WorldBible:
    conn.execute(
        "INSERT OR REPLACE INTO world_bible (world_id, premise, aether_system, the_fall, history, "
        "layers, peoples, factions_overview, themes, tone, status, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (bible.world_id, bible.premise, bible.aether_system, bible.the_fall, bible.history,
         json.dumps(bible.layers), bible.peoples, bible.factions_overview,
         json.dumps(bible.themes), bible.tone, bible.status, bible.source),
    )
    conn.commit()
    return bible


def render_world_bible(bible: WorldBible) -> str:
    """Compact canon block, prepended to WORLD FACTS during retrieval."""
    parts = ["WORLD BIBLE (CANON — every story must stay consistent with this):"]
    if bible.premise:
        parts.append(f"PREMISE: {bible.premise}")
    if bible.aether_system:
        parts.append(f"AETHER SYSTEM: {bible.aether_system}")
    if bible.the_fall:
        parts.append(f"THE FALL: {bible.the_fall}")
    if bible.history:
        parts.append(f"HISTORY: {bible.history}")
    if bible.layers:
        layer_bits = "; ".join(f"{k}: {v}" for k, v in bible.layers.items() if v)
        if layer_bits:
            parts.append(f"LAYERS: {layer_bits}")
    if bible.peoples:
        parts.append(f"PEOPLES: {bible.peoples}")
    if bible.factions_overview:
        parts.append(f"FACTIONS: {bible.factions_overview}")
    if bible.themes:
        parts.append("THEMES: " + ", ".join(bible.themes))
    if bible.tone:
        parts.append(f"TONE: {bible.tone}")
    return "\n".join(parts) if len(parts) > 1 else ""


def _build_bible(world_id, data: dict) -> WorldBible:
    """Coerce a parsed JSON object into a WorldBible, ensuring all five layers exist."""
    layers = data.get("layers") or {}
    if not isinstance(layers, dict):
        layers = {}
    layers = {str(k): str(v) for k, v in layers.items()}
    for name in _LAYERS:
        layers.setdefault(name, "")
    themes = data.get("themes") or []
    if not isinstance(themes, list):
        themes = []
    return WorldBible(
        world_id=world_id,
        premise=str(data.get("premise", "")),
        aether_system=str(data.get("aether_system", "")),
        the_fall=str(data.get("the_fall", "")),
        history=str(data.get("history", "")),
        layers=layers,
        peoples=str(data.get("peoples", "")),
        factions_overview=str(data.get("factions_overview", "")),
        themes=[str(t) for t in themes],
        tone=str(data.get("tone", "")),
        status="draft", source="ai",
    )


def verify_bible(bible_text: str, router: ModelRouter, *, generator_model: str,
                 threshold: int) -> VerifierVerdict:
    """Cross-model check of the draft. On unparseable output, accept (keep the draft)."""
    messages = [
        {"role": "system", "content": _BIBLE_VERIFY_SYSTEM},
        {"role": "user", "content": f"WORLD BIBLE:\n{bible_text}\n\n"
                                    f"Acceptance threshold per score: {threshold}."},
    ]
    try:
        result = router.complete("verifier", messages, json_mode=True, exclude_model=generator_model)
        data = extract_json_object(result.content)
        if not isinstance(data, dict):
            raise ValueError("non-object verdict")
        return VerifierVerdict(**data)
    except (ValueError, TypeError, RuntimeError):
        # Verifier unavailable or unparseable — don't block the draft.
        return VerifierVerdict(verdict="accept", scores={}, issues=["unverified: verifier unavailable"])


def generate_world_bible(world_id, conn: sqlite3.Connection, router: ModelRouter, *,
                         max_repair: int = 1, threshold: int = 6) -> WorldBible:
    """Draft the bible, verify it cross-model, and repair empty/conflict fields."""
    facts = _seed_facts(world_id, conn)
    base_user = f"WORLD SEED FACTS:\n{facts}\n\nWrite the world bible."
    fix_hints: list[str] = []
    bible: WorldBible | None = None
    last_parse_error: ValueError | None = None

    for attempt in range(max_repair + 1):
        user = base_user
        if fix_hints:
            user += ("\n\nYOUR PREVIOUS DRAFT WAS REJECTED. Fix exactly these problems and "
                     "return the COMPLETE corrected JSON:\n- " + "\n- ".join(fix_hints))
        messages = [
            {"role": "system", "content": _BIBLE_SYSTEM},
            {"role": "user", "content": user},
        ]
        result = router.complete("director", messages, json_mode=True)
        try:
            data = extract_json_object(result.content)
            if not isinstance(data, dict):
                raise ValueError("worldbuilder returned a non-object world bible")
        except ValueError as exc:
            # Free models occasionally emit prose/empty instead of JSON; retry while
            # repair budget remains instead of failing the whole request.
            last_parse_error = exc
            fix_hints = ["Your previous reply was not valid JSON. Reply with ONLY the JSON object."]
            if attempt == max_repair:
                if bible is not None:
                    break  # fall back to an earlier good draft
                raise ValueError("worldbuilder returned non-JSON world bible") from exc
            continue
        bible = _build_bible(world_id, data)

        verdict = verify_bible(render_world_bible(bible), router,
                               generator_model=result.model, threshold=threshold)
        if verdict.passed(threshold) or verdict.verdict == "accept" or not verdict.fix_hints:
            break
        if attempt == max_repair:  # out of repair attempts; keep best effort
            break
        fix_hints = verdict.fix_hints

    if bible is None:  # never produced a parseable draft
        raise ValueError("worldbuilder returned non-JSON world bible") from last_parse_error
    return save_world_bible(conn, bible)
