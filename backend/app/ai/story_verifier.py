from __future__ import annotations
import json
from app.ai.model_router import ModelRouter
from app.models.schemas import VerifierVerdict

_SYSTEM = (
    "You are a strict story editor. Judge the SCENE for coherence, character voice, "
    "tone/pacing, continuity, and grounding in the provided CONTEXT. "
    "Reply with ONLY a JSON object: "
    '{"verdict":"accept|revise|reject","scores":{"coherence":0-10,"voice":0-10,'
    '"grounding":0-10},"issues":[],"fix_hints":[]}'
)


def verify_scene(scene_text: str, packed_context: str, router: ModelRouter, *,
                 generator_model: str, threshold: int) -> VerifierVerdict:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"CONTEXT:\n{packed_context}\n\nSCENE:\n{scene_text}\n\n"
                                    f"Acceptance threshold per score: {threshold}."},
    ]
    result = router.complete("verifier", messages, json_mode=True, exclude_model=generator_model)
    try:
        data = json.loads(result.content)
        return VerifierVerdict(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return VerifierVerdict(verdict="reject", issues=["unparseable verifier output"])
