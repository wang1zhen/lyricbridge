"""
API router package.

Routers here organise endpoints by domain (search, export, settings, health).
"""

from fastapi import APIRouter

from . import health, search, settings, export


def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router, prefix="/health", tags=["health"])
    router.include_router(settings.router, prefix="/settings", tags=["settings"])
    router.include_router(search.router, prefix="/search", tags=["search"])
    router.include_router(export.router, prefix="/export", tags=["export"])
    return router


__all__ = ["create_api_router"]
