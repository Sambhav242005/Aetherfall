from __future__ import annotations
import json
import sqlite3
import uuid
from app.ai.json_utils import extract_json_object
from app.ai.model_router import ModelRouter
from app.ai.rag.retriever import Retriever
from app.ai.rag.story_bible import StoryBible
from app.ai.ai_validator import validate_proposal
from app.ai.story_verifier import verify_scene
from app.ai.story_worker import draft_scene, revise_scene, summarize
from app.models.schemas import StoryArc, StoryBeat, Scene, AIProposal

_OUTLINE_SYSTEM = (
    "You are a game story director. Using the WORLD FACTS, design a grounded multi-act arc. "
    "Reply with ONLY JSON: "
    '{"title":"","premise":"","theme":"","beats":[{"act":1,"summary":"",'
    '"location_ids":[],"character_ids":[],"faction_ids":[]}]}. '
    "Only reference ids present in WORLD FACTS."
)


def generate_outline(world_id, conn: sqlite3.Connection, router: ModelRouter,
                     retriever: Retriever) -> StoryArc:
    facts = retriever.world_facts()
    messages = [
        {"role": "system", "content": _OUTLINE_SYSTEM},
        {"role": "user", "content": f"WORLD FACTS:\n{facts}\n\nDesign the arc."},
    ]
    raw = router.complete("director", messages, json_mode=True).content
    try:
        data = extract_json_object(raw)
    except ValueError as exc:
        raise ValueError("director returned non-JSON story outline") from exc
    if not isinstance(data, dict):
        raise ValueError("director returned a non-object story outline")
    arc_id = f"arc_{uuid.uuid4().hex[:8]}"
    beat_ids: list[str] = []
    for i, b in enumerate(data.get("beats", [])):
        beat = StoryBeat(id=f"beat_{uuid.uuid4().hex[:8]}", arc_id=arc_id,
                         act=int(b.get("act", 1)), order=i, summary=b.get("summary", ""),
                         location_ids=b.get("location_ids", []),
                         character_ids=b.get("character_ids", []),
                         faction_ids=b.get("faction_ids", []))
        beat_ids.append(beat.id)
        conn.execute(
            'INSERT INTO story_beats (id, arc_id, act, "order", summary, location_ids, '
            "character_ids, faction_ids, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (beat.id, beat.arc_id, beat.act, beat.order, beat.summary,
             json.dumps(beat.location_ids), json.dumps(beat.character_ids),
             json.dumps(beat.faction_ids), beat.status),
        )
    arc = StoryArc(id=arc_id, world_id=world_id, title=data.get("title", ""),
                   premise=data.get("premise", ""), theme=data.get("theme", ""), beats=beat_ids)
    conn.execute("INSERT INTO story_arcs (id, world_id, title, premise, theme, beats) VALUES (?,?,?,?,?,?)",
                 (arc.id, arc.world_id, arc.title, arc.premise, arc.theme, json.dumps(arc.beats)))
    conn.commit()
    return arc


def _load_beats(conn, arc_id) -> list[StoryBeat]:
    rows = conn.execute('SELECT * FROM story_beats WHERE arc_id = ? ORDER BY "order"', (arc_id,)).fetchall()
    return [StoryBeat(id=r["id"], arc_id=r["arc_id"], act=r["act"], order=r["order"],
                      summary=r["summary"], location_ids=json.loads(r["location_ids"]),
                      character_ids=json.loads(r["character_ids"]),
                      faction_ids=json.loads(r["faction_ids"]), status=r["status"]) for r in rows]


def _persist_scene(conn, scene: Scene) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO scenes (id, beat_id, title, prose, dialogue, "
        "storyboard_card_id, revealed_information, status) VALUES (?,?,?,?,?,?,?,?)",
        (scene.id, scene.beat_id, scene.title, scene.prose, json.dumps(scene.dialogue),
         scene.storyboard_card_id, json.dumps(scene.revealed_information), scene.status),
    )
    conn.commit()


def generate_story(world_id, conn: sqlite3.Connection, router: ModelRouter,
                   retriever: Retriever, bible: StoryBible, *, max_repair: int,
                   threshold: int) -> StoryArc:
    arc = generate_outline(world_id, conn, router, retriever)
    for beat in _load_beats(conn, arc.id):
        ctx = retriever.retrieve(beat.summary, k=5, location_ids=beat.location_ids or None,
                                 character_ids=beat.character_ids or None,
                                 faction_ids=beat.faction_ids or None)
        packed = ctx.pack(char_budget=6000)

        proposal = AIProposal(id=f"prop_{uuid.uuid4().hex[:8]}", proposal_type="scene",
                              referenced_world_ids=beat.location_ids + beat.character_ids + beat.faction_ids,
                              payload={"location_id": beat.location_ids[0] if beat.location_ids else None,
                                       "character_ids": beat.character_ids,
                                       "faction_ids": beat.faction_ids})
        scene = Scene(id=f"scene_{uuid.uuid4().hex[:8]}", beat_id=beat.id,
                      title=beat.summary[:60], revealed_information=[])

        reasons = validate_proposal(proposal, conn)
        if reasons:
            scene.status = "rejected"
            scene.prose = "; ".join(reasons)
            _persist_scene(conn, scene)
            continue

        text, gen_model = draft_scene(beat, packed, router)
        approved = False
        for attempt in range(max_repair + 1):
            verdict = verify_scene(text, packed, router, generator_model=gen_model, threshold=threshold)
            if verdict.passed(threshold):
                approved = True
                break
            if verdict.verdict == "reject" or not verdict.fix_hints:
                break
            if attempt == max_repair:  # final verify failed; no repair attempts left
                break
            text, gen_model = revise_scene(text, verdict.fix_hints, packed, router)

        scene.prose = text
        scene.status = "approved" if approved else "needs_human_review"
        _persist_scene(conn, scene)
        if approved:
            bible.add_entry(world_id, "scene", scene.id, summarize(text, router))
    return arc
