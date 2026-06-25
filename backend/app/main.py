from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_world import router as world_router
from app.api.routes_ai import router as ai_router

app = FastAPI(
    title="Aetherworld Engine",
    description="Backend API for Aetherworld — a web-based 2D/2.5D systemic open-world RPG",
    version="0.1.0",
)

# Local-dev CORS: lets the static web canvas (served on a different port) call the API.
# Tighten allow_origins to specific hosts before any non-local deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(world_router)
app.include_router(ai_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
