from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import create_api_router
from app.config import AppSettings, get_settings


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="LyricBridge backend",
        description="FastAPI backend that mirrors the functionality of 163MusicLyrics (LyricBridge)",
        version=settings.version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(create_api_router())

    return app


app = create_app()
