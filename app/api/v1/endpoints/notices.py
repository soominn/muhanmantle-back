"""Public notices. Markdown files on disk; no session and no database."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.notices import list_notices

router = APIRouter(prefix="/api", tags=["notices"])


@router.get("/notices")
def get_notices():
    return {"items": list_notices()}
