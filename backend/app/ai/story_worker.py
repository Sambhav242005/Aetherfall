from __future__ import annotations
from app.ai.model_router import ModelRouter
from app.models.schemas import StoryBeat


def draft_scene(beat: StoryBeat, packed_context: str, router: ModelRouter) -> tuple[str, str]:
    messages = [
        {"role": "system", "content": "You are a game scene writer. Write vivid, grounded prose "
                                      "consistent with the CONTEXT. Do not invent locations or "
                                      "characters absent from CONTEXT."},
        {"role": "user", "content": f"CONTEXT:\n{packed_context}\n\nBEAT (act {beat.act}): "
                                    f"{beat.summary}\n\nWrite the scene."},
    ]
    res = router.complete("worker", messages, temperature=0.9)
    return res.content, res.model


def revise_scene(previous: str, fix_hints: list[str], packed_context: str,
                 router: ModelRouter) -> tuple[str, str]:
    hints = "; ".join(fix_hints)
    messages = [
        {"role": "system", "content": "Revise the SCENE to fix the listed problems while keeping "
                                      "what works. Stay grounded in CONTEXT."},
        {"role": "user", "content": f"CONTEXT:\n{packed_context}\n\nSCENE:\n{previous}\n\n"
                                    f"FIXES REQUIRED: {hints}"},
    ]
    res = router.complete("worker", messages, temperature=0.7)
    return res.content, res.model


def summarize(text: str, router: ModelRouter) -> str:
    messages = [
        {"role": "system", "content": "Summarize in at most two sentences, preserving named "
                                      "characters, locations, and revealed facts."},
        {"role": "user", "content": text},
    ]
    return router.complete("worker", messages, temperature=0.2).content
