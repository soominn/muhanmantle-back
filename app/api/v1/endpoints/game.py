"""Game session API: HttpOnly cookie + MariaDB (no client-side localStorage for game state)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services import game_session_service as gss

router = APIRouter(prefix="/api/game", tags=["game"])


def _session_id_from_request(request: Request) -> str | None:
    """Prefer HttpOnly cookie; accept X-Game-Session when cookies do not cross origins."""
    raw = request.cookies.get(settings.session_cookie_name)
    if raw:
        try:
            uuid.UUID(raw)
            return raw
        except (ValueError, TypeError):
            pass
    hdr = request.headers.get("X-Game-Session") or request.headers.get("x-game-session")
    if not hdr:
        return None
    hdr = hdr.strip()
    try:
        uuid.UUID(hdr)
        return hdr
    except (ValueError, TypeError):
        return None


class GuessBody(BaseModel):
    word: str


def _attach_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="none" if settings.session_cookie_secure else "lax",
        path="/",
    )


def _resolve_row(request: Request, response: Response, db: Session):
    sid = _session_id_from_request(request)
    row = gss.get_or_create_session(db, sid)
    _attach_session_cookie(response, row.id)
    return row


@router.get("/session")
def get_session(request: Request, response: Response, db: Session = Depends(get_db)):
    row = _resolve_row(request, response, db)
    # revealed_answer stays null until give-up, then survives refresh.
    return gss.state_with_reveal(db, row)


@router.post("/session/guess")
def post_guess(
    body: GuessBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    row = _resolve_row(request, response, db)
    try:
        state, duplicate = gss.submit_guess(db, row, body.word)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {**state, "duplicate": duplicate}


@router.post("/session/reset")
def post_reset(request: Request, response: Response, db: Session = Depends(get_db)):
    row = _resolve_row(request, response, db)
    row = gss.reset_session(db, row)
    return gss.state_with_reveal(db, row)


@router.post("/session/give-up")
def post_give_up(request: Request, response: Response, db: Session = Depends(get_db)):
    row = _resolve_row(request, response, db)
    try:
        return gss.give_up(db, row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
