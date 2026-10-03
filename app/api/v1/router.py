from fastapi import APIRouter

from app.api.v1.endpoints import game, health, notices

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(game.router)
api_router.include_router(notices.router)
