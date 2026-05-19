from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-game-session",
    "x-requested-with",
]


def add_cors_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=CORS_METHODS,
        allow_headers=CORS_HEADERS,
    )
