from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GameShout(Base):
    """One row per (word, session) across every puzzle. Repeats do not add a row."""

    __tablename__ = "game_shout"

    # Leading with word keeps the global GROUP BY word ranking scan local.
    word: Mapped[str] = mapped_column(String(255), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
