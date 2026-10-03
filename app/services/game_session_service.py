"""Server-side game state: pick answers, score guesses, sort rows (matches frontend UX)."""

from __future__ import annotations

import math
import random
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.game_session import GameSession
from app.repositories.game_session_repository import GameSessionRepository
from app.repositories.simword_repository import SimwordRepository
from app.services import model_loader, similarity_service
from app.utils.word_input import is_valid_korean_word

# Normalized embedding cosine is in [-1, 1]; treat as correct when numerically ~1.
_COSINE_FULL_SCORE_TOL = 1e-3


def _guess_cosine_similarity(g: dict[str, Any]) -> float:
    if "similarity" in g and g["similarity"] is not None:
        return float(g["similarity"])
    legacy = g.get("similarityPct")
    if legacy is None:
        return 0.0
    return float(legacy) / 100.0


def _enrich_guess_similarity(g: dict[str, Any]) -> dict[str, Any]:
    """API always exposes cosine `similarity` in [-1, 1]; map legacy similarityPct (×100 int)."""
    if "similarity" in g and g["similarity"] is not None:
        out = dict(g)
        out["similarity"] = round(float(g["similarity"]), 6)
        return out
    legacy = g.get("similarityPct")
    if legacy is not None:
        out = dict(g)
        out["similarity"] = round(float(legacy) / 100.0, 6)
        return out
    return {**g, "similarity": 0.0}


def pick_answer_id(total: int, previous_answers: list[int]) -> tuple[int, list[int]]:
    """Return (new_answer_id, updated_history). If all ids exhausted, clear history (same as client)."""
    if total <= 0:
        raise ValueError("total must be positive")

    history = list(previous_answers)
    attempts = 0
    while True:
        candidate = random.randint(1, total)
        attempts += 1
        if attempts > total:
            history = []
            candidate = random.randint(1, total)
        if candidate not in history:
            new_history = [*history, candidate]
            return candidate, new_history


def sort_guesses(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not results:
        return results
    enriched = [_enrich_guess_similarity(g) for g in results]
    latest = max(enriched, key=lambda r: int(r["attemptNumber"]))
    rest = [r for r in enriched if r is not latest]
    rest.sort(key=lambda r: _guess_cosine_similarity(r), reverse=True)
    return [latest, *rest]


def public_state(db: Session, row: GameSession) -> dict[str, Any]:
    """Fields shared by session, guess, and reset. Never includes the answer word."""
    return {
        "session_id": row.id,
        "answer_id": row.answer_id,
        "total_count": SimwordRepository.count_answer_words(db),
        "guesses": sort_guesses(list(row.guesses or [])),
        "is_correct": bool(row.is_correct),
        "correct_attempt_count": int(row.correct_attempt_count or 0),
    }


def _revealed_answer(db: Session, row: GameSession) -> dict[str, Any] | None:
    """Screen number + answer word, only after give-up. `number` is `answer_id`.

    The frontend already renders `answer_id` as "N번째 정답", so give-up uses that same N.
    """
    if not row.gave_up or row.answer_id is None:
        return None
    answer = SimwordRepository.get_answer_by_id(db, int(row.answer_id))
    if answer is None:
        return None
    return {"number": int(row.answer_id), "word": answer.answer_word}


def state_with_reveal(db: Session, row: GameSession) -> dict[str, Any]:
    """public_state plus `revealed_answer` (`null` until this puzzle was given up)."""
    state = public_state(db, row)
    state["revealed_answer"] = _revealed_answer(db, row)
    return state


def create_new_session_row(db: Session, total: int) -> GameSession:
    if total <= 0:
        return GameSessionRepository.add(
            db,
            GameSession(
                id=str(uuid.uuid4()),
                answer_id=None,
                answer_history=[],
                guesses=[],
                is_correct=False,
                correct_attempt_count=0,
                gave_up=False,
            ),
        )
    new_id, history = pick_answer_id(total, [])
    return GameSessionRepository.add(
        db,
        GameSession(
            id=str(uuid.uuid4()),
            answer_id=new_id,
            answer_history=history,
            guesses=[],
            is_correct=False,
            correct_attempt_count=0,
            gave_up=False,
        ),
    )


def get_or_create_session(db: Session, cookie_id: str | None) -> GameSession:
    if cookie_id:
        existing = GameSessionRepository.get_by_id(db, cookie_id)
        if existing is not None:
            return existing

    total = SimwordRepository.count_answer_words(db)
    return create_new_session_row(db, total)


def reset_session(db: Session, row: GameSession) -> GameSession:
    total = SimwordRepository.count_answer_words(db)
    if total <= 0:
        row.answer_id = None
        row.answer_history = []
        row.guesses = []
        row.is_correct = False
        row.correct_attempt_count = 0
        row.gave_up = False
        return GameSessionRepository.save(db, row)

    prev = [int(x) for x in (row.answer_history or [])]
    new_id, history = pick_answer_id(total, prev)
    row.answer_id = new_id
    row.answer_history = history
    row.guesses = []
    row.is_correct = False
    row.correct_attempt_count = 0
    row.gave_up = False
    return GameSessionRepository.save(db, row)


def give_up(db: Session, row: GameSession) -> dict[str, Any]:
    """Reveal the current answer and keep that disclosure on the session."""
    if row.answer_id is None:
        raise ValueError("no active answer")

    answer = SimwordRepository.get_answer_by_id(db, int(row.answer_id))
    if answer is None:
        raise LookupError("answer not found")

    if not row.gave_up:
        row.gave_up = True
        GameSessionRepository.save(db, row)
    return state_with_reveal(db, row)


def submit_guess(
    db: Session,
    row: GameSession,
    raw_word: str,
) -> tuple[dict[str, Any], bool]:
    """Returns (state dict, duplicate_flag). On duplicate, DB is unchanged and duplicate_flag True."""

    word = (raw_word or "").strip()
    if not word:
        raise ValueError("empty word")

    if not is_valid_korean_word(word):
        raise ValueError("invalid word")

    aid = row.answer_id
    if aid is None:
        raise ValueError("no active answer")

    answer = SimwordRepository.get_answer_by_id(db, aid)
    if answer is None:
        raise LookupError("answer not found")

    answer_word = answer.answer_word
    similarity_service.ensure_cache_built(db)

    if not model_loader.word_in_model(answer_word):
        raise LookupError("answer not in model")

    if not model_loader.word_in_model(word):
        raise ValueError(f"Input word '{word}' not found in the model.")

    guesses: list[dict[str, Any]] = list(row.guesses or [])
    if any(g.get("word") == word for g in guesses):
        return public_state(db, row), True

    cosine_sim, (rank, base_word_exists) = similarity_service.compute_similarity_and_rank(
        word, answer_word
    )

    if not base_word_exists:
        if SimwordRepository.insert_base_word_if_absent(db, word):
            model_loader.append_base_word_to_cache(word)
        rank = "?"

    is_full_score = word == answer_word or math.isclose(
        cosine_sim, 1.0, rel_tol=0.0, abs_tol=_COSINE_FULL_SCORE_TOL
    )
    if is_full_score:
        rank = "정답!"

    new_guess: dict[str, Any] = {
        "attemptNumber": len(guesses) + 1,
        "word": word,
        "similarity": round(float(cosine_sim), 6),
        "rank": rank,
    }
    merged = sort_guesses([*guesses, new_guess])
    row.guesses = merged

    if is_full_score:
        row.is_correct = True
        row.correct_attempt_count = len(guesses) + 1

    GameSessionRepository.save(db, row)
    return public_state(db, row), False
