from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.data.repository import load_repository

DATA_DIR_ENV = "MONA_DATA_DIR"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def create_app(data_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        directory = data_dir or Path(os.environ.get(DATA_DIR_ENV, DEFAULT_DATA_DIR))
        app.state.repository = load_repository(directory)
        yield

    app = FastAPI(title="Mona funding matcher", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
