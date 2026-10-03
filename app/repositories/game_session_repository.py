from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.game_session import GameSession
from app.models.game_shout import GameShout


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

    @staticmethod
    def record_shout(db: Session, session_id: str, word: str) -> None:
        """Remember that this session submitted the word, once across all puzzles.

        Does not commit; the caller commits together with the guess.
        """
        exists = db.scalar(
            select(GameShout.session_id).where(
                GameShout.word == word,
                GameShout.session_id == session_id,
            )
        )
        if exists is not None:
            return
        try:
            with db.begin_nested():
                db.add(GameShout(word=word, session_id=session_id))
                db.flush()
        except IntegrityError:
            return

    @staticmethod
    def shout_ranking(db: Session, limit: int) -> list[tuple[str, int]]:
        """Every submitted word, highest count first. Ties break by word ascending."""
        count_col = func.count().label("cnt")
        stmt = (
            select(GameShout.word, count_col)
            .group_by(GameShout.word)
            .order_by(count_col.desc(), GameShout.word.asc())
            .limit(limit)
        )
        return [(word, int(count)) for word, count in db.execute(stmt).all()]
