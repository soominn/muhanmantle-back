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
    def record_shout(db: Session, session_id: str, answer_id: int, word: str) -> None:
        """Insert a shout if this session has not already submitted the word for the answer.

        Does not commit; the caller commits together with the guess.
        """
        exists = db.scalar(
            select(GameShout.session_id).where(
                GameShout.answer_id == answer_id,
                GameShout.word == word,
                GameShout.session_id == session_id,
            )
        )
        if exists is not None:
            return
        try:
            with db.begin_nested():
                db.add(
                    GameShout(
                        answer_id=answer_id,
                        word=word,
                        session_id=session_id,
                    )
                )
                db.flush()
        except IntegrityError:
            # Concurrent submit of the same word already stored this shout.
            return

    @staticmethod
    def shout_ranking(
        db: Session, answer_id: int, limit: int
    ) -> list[tuple[str, int]]:
        """Words shouted for this answer, highest count first. Ties break by word ascending."""
        count_col = func.count().label("cnt")
        stmt = (
            select(GameShout.word, count_col)
            .where(GameShout.answer_id == answer_id)
            .group_by(GameShout.word)
            .order_by(count_col.desc(), GameShout.word.asc())
            .limit(limit)
        )
        return [(word, int(count)) for word, count in db.execute(stmt).all()]
