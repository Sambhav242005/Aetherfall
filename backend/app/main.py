from __future__ import annotations
from fastapi import FastAPI
from app.api.routes_world import router as world_router

app = FastAPI(
    title="Aetherworld Engine",
    description="Backend API for Aetherworld — a web-based 2D/2.5D systemic open-world RPG",
    version="0.1.0",
)

app.include_router(world_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
