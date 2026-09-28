"""FastAPI 入口 v0.3。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    books,
    bridge,
    crossover,
    health,
    personas,
    scene_cards,
    theater,
)
from app.api import settings as settings_api
from app.config import get_settings
from app.queue import get_queue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = get_settings()
    cfg.resolved_books_dir.mkdir(parents=True, exist_ok=True)
    cfg.resolved_artifacts_dir.mkdir(parents=True, exist_ok=True)
    queue = get_queue()
    await queue.start()
    yield
    await queue.stop()


def create_app() -> FastAPI:
    cfg = get_settings()
    app = FastAPI(
        title=cfg.app_name,
        version="0.3.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    app.include_router(books.router, prefix="/api/v1/books", tags=["books"])
    app.include_router(personas.router, prefix="/api/v1/books", tags=["personas"])
    app.include_router(theater.router, prefix="/api/v1/theater", tags=["theater"])
    app.include_router(crossover.router, prefix="/api/v1/theater", tags=["crossover"])
    app.include_router(scene_cards.router, prefix="/api/v1/scene-cards", tags=["cards"])
    app.include_router(
        settings_api.router, prefix="/api/v1/settings", tags=["settings"]
    )
    app.include_router(bridge.router, prefix="/api/v1", tags=["bridge"])
    return app


app = create_app()


def run() -> None:
    import uvicorn

    cfg = get_settings()
    uvicorn.run("app.main:app", host=cfg.host, port=cfg.port, reload=cfg.debug)


if __name__ == "__main__":
    run()
