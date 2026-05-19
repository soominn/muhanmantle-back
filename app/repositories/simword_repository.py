"""
Database access layer for the simword domain.

All SQL operations are centralised here so that endpoints and services
never construct queries directly.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.answer_word import AnswerWord
from app.models.base_word import BaseWord


class SimwordRepository:
    @staticmethod
    def get_answer_by_id(db: Session, answer_id: int) -> AnswerWord | None:
        return db.get(AnswerWord, answer_id)

    @staticmethod
    def count_answer_words(db: Session) -> int:
        return db.scalar(select(func.count()).select_from(AnswerWord)) or 0

    @staticmethod
    def get_all_base_words(db: Session) -> list[str]:
        return list(db.scalars(select(BaseWord.base_word)))

    @staticmethod
    def insert_base_word_if_absent(db: Session, word: str) -> bool:
        """Persist *word* to BaseWord. Returns True if inserted, False on duplicate."""
        try:
            db.add(BaseWord(base_word=word))
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False
