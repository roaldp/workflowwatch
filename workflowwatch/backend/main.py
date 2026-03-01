import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import close_db, init_db
from .routers.auto_label import router as auto_label_router
from .routers.label_rules import router as label_rules_router
from .routers.sessions import router as sessions_router
from .routers.suggestions import router as suggestions_router
from .routers.timeline import router as timeline_router
from .routers.workflows import router as workflows_router
from .services.aw_service import AWService
from .services.embedding_service import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting WorkflowWatch backend")

    init_db()
    app.state.db_path = settings.ww_db_path

    aw = AWService()
    await aw.startup()
    app.state.aw_service = aw

    # Seed default workflows on first launch
    from .services.workflow_service import seed_default_workflows
    seeded = seed_default_workflows()
    if seeded:
        logger.info("Seeded %d default workflows", seeded)

    # WP-7: populate label cache from existing sessions
    from .services.cache_service import populate_from_sessions
    n = populate_from_sessions()
    logger.info("Label cache: %d entries loaded from session history", n)

    # WP-7: initialize embedding service (lazy — model loads on first query)
    embedding_service = EmbeddingService()
    app.state.embedding_service = embedding_service

    logger.info("WorkflowWatch backend ready on %s:%s", settings.ww_host, settings.ww_port)
    yield

    await aw.shutdown()
    close_db()
    logger.info("WorkflowWatch backend stopped")


app = FastAPI(
    title="WorkflowWatch",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5700",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5700",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(timeline_router)
app.include_router(workflows_router)
app.include_router(sessions_router)
app.include_router(suggestions_router)
app.include_router(auto_label_router)
app.include_router(label_rules_router)


@app.get("/")
def root():
    """Root route so opening the server URL in a browser returns something useful."""
    return {
        "name": "WorkflowWatch",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "timeline": "/api/v1/timeline?date=YYYY-MM-DD",
    }


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.ww_host,
        port=settings.ww_port,
        reload=True,
    )
