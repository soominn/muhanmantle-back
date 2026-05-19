from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.game_session import GameSession


class GameSessionRepository:
    @staticmethod
    def get_by_id(db: Session, session_id: str) -> GameSession | None:
        return db.get(GameSession, session_id)

    @staticmethod
    def add(db: Session, row: GameSession) -> GameSession:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def save(db: Session, row: GameSession) -> GameSession:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
