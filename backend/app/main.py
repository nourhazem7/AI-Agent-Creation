from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine, run_lightweight_migrations
from app.routers import (
    agent_shares,
    agents,
    auth,
    chat,
    companies,
    database_connections,
    health,
    knowledge_assets,
    knowledge_summary,
    validation,
)

# Import models so their tables are registered on Base.metadata before create_all().
import app.models  # noqa: F401

settings = get_settings()

app = FastAPI(
    title="AgentForge API",
    description="Platform layer around the text2sql reasoning engine.",
    version="0.1.0",
)

# Explicit origin allowlist — deliberately not "*" (contrast with the text2sql/api.py prototype).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(database_connections.router, prefix="/api")
app.include_router(knowledge_assets.router, prefix="/api")
app.include_router(knowledge_summary.router, prefix="/api")
app.include_router(validation.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(agent_shares.router, prefix="/api")
app.include_router(companies.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
