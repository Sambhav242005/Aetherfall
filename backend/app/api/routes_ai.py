from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from app.config import get_settings
from app.ai.ai_client import OpenRouterClient
from app.ai.model_router import ModelRouter
from app.ai.rag.embeddings import HashEmbedder
from app.ai.rag.vector_store import VectorStore
from app.ai.rag.story_bible import StoryBible
from app.ai.rag.retriever import Retriever
from app.ai.story_director import generate_story
from app.ai.ai_validator import validate_proposal
from app.persistence.database import get_connection, init_db
from app.models.schemas import AIProposal

router = APIRouter(prefix="/api/ai")


def get_router() -> ModelRouter:
    s = get_settings()
    client = OpenRouterClient(s.openrouter_api_key, s.openrouter_base_url, s.request_timeout)
    return ModelRouter(client, s)


@router.post("/story/generate")
def generate(world_id: str, model_router: ModelRouter = Depends(get_router)):
    init_db()
    s = get_settings()
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM worlds WHERE id = ?", (world_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="World not found")
        embedder = HashEmbedder(dim=s.embedding_dim)
        bible = StoryBible(conn, embedder, VectorStore(conn, embedder.dim))
        retriever = Retriever(conn, bible)
        arc = generate_story(world_id, conn, model_router, retriever, bible,
                             max_repair=s.max_repair_attempts, threshold=s.verifier_threshold)
        scene_count = conn.execute(
            "SELECT COUNT(*) AS c FROM scenes s JOIN story_beats b ON s.beat_id = b.id "
            "WHERE b.arc_id = ?", (arc.id,)).fetchone()["c"]
        return {"arc": arc.model_dump(mode="json"), "scene_count": scene_count}
    finally:
        conn.close()


@router.get("/story/{world_id}")
def get_story(world_id: str):
    conn = get_connection()
    try:
        arcs = [dict(r) for r in conn.execute("SELECT * FROM story_arcs WHERE world_id = ?", (world_id,)).fetchall()]
        arc_ids = [a["id"] for a in arcs]
        beats, scenes = [], []
        if arc_ids:
            marks = ",".join("?" for _ in arc_ids)
            beats = [dict(r) for r in conn.execute(
                f'SELECT * FROM story_beats WHERE arc_id IN ({marks}) ORDER BY "order"', arc_ids).fetchall()]
            beat_ids = [b["id"] for b in beats]
            if beat_ids:
                bmarks = ",".join("?" for _ in beat_ids)
                scenes = [dict(r) for r in conn.execute(
                    f"SELECT * FROM scenes WHERE beat_id IN ({bmarks})", beat_ids).fetchall()]
        return {"arcs": arcs, "beats": beats, "scenes": scenes}
    finally:
        conn.close()


@router.post("/proposal/validate")
def validate(proposal: AIProposal):
    conn = get_connection()
    try:
        reasons = validate_proposal(proposal, conn)
        return {"valid": len(reasons) == 0, "reasons": reasons}
    finally:
        conn.close()
