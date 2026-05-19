"""
Similarity computation service.

Orchestrates model_loader (ML state) and the repository (DB reads) to:
  - ensure the BaseWord cache is up to date before any computation
  - compute cosine similarity between two words
  - derive top-500 lists and per-word ranks
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.services import model_loader

# answer_word -> (base_vecs @ ans_vec), reused across guesses with the same 정답 단어
_MAX_ANSWER_SIMS_ENTRIES = 64
_answer_sims_lru: OrderedDict[tuple[str, int], np.ndarray] = OrderedDict()


def _touch_answer_sims_cache(key: tuple[str, int], sims: np.ndarray) -> None:
    _answer_sims_lru[key] = sims
    _answer_sims_lru.move_to_end(key)
    while len(_answer_sims_lru) > _MAX_ANSWER_SIMS_ENTRIES:
        _answer_sims_lru.popitem(last=False)


def _answer_sims_for(answer_word: str, ans_vec: np.ndarray) -> Optional[np.ndarray]:
    """Dot products of every BaseWord row with *ans_vec*; cached per (답 단어, matrix generation)."""
    gen = model_loader.base_matrix_generation()
    key = (answer_word, gen)
    if key in _answer_sims_lru:
        _answer_sims_lru.move_to_end(key)
        return _answer_sims_lru[key]

    _, base_vecs = model_loader.get_cache()
    if base_vecs is None or base_vecs.shape[0] == 0:
        return None
    sims = base_vecs @ ans_vec
    _touch_answer_sims_cache(key, sims)
    return sims


def ensure_cache_built(db: Session) -> None:
    """Rebuild the BaseWord similarity matrix from DB when the dirty flag is set."""
    if not model_loader.needs_rebuild():
        return
    # Import here to avoid circular imports at module load time
    from app.repositories.simword_repository import SimwordRepository
    words = SimwordRepository.get_all_base_words(db)
    model_loader.build_baseword_matrix(words)


def get_top_500_similarities(answer_word: str) -> Optional[list[dict]]:
    """Return top-500 BaseWord entries ordered by similarity to *answer_word*.

    Returns None when the model or cache is unavailable (caller should 404).
    """
    base_words, base_vecs = model_loader.get_cache()
    if base_vecs is None or not base_words:
        return None

    ans_vec = model_loader.get_normalized_vector(answer_word)
    if ans_vec is None:
        return None

    sims = _answer_sims_for(answer_word, ans_vec)
    if sims is None:
        return None
    result = model_loader.top_k_by_similarity(
        sims, base_words, k=500, exclude_word=answer_word
    )
    return result if result else None


def compute_input_similarity(input_word: str, answer_word: str) -> float:
    """Return cosine similarity in [-1, 1] (L2-normalized dot product)."""
    in_vec = model_loader.get_normalized_vector(input_word)
    ans_vec = model_loader.get_normalized_vector(answer_word)
    if in_vec is None or ans_vec is None:
        return 0.0
    return round(float(in_vec @ ans_vec), 6)


def compute_similarity_and_rank(
    input_word: str,
    answer_word: str,
) -> tuple[float, tuple[int | str, bool]]:
    """One-pass cosine similarity + rank; cosine is in [-1, 1] for normalized embeddings."""
    in_vec = model_loader.get_normalized_vector(input_word)
    ans_vec = model_loader.get_normalized_vector(answer_word)
    if in_vec is None or ans_vec is None:
        return 0.0, ("순위 밖", False)

    cosine = round(float(in_vec @ ans_vec), 6)

    _, base_vecs = model_loader.get_cache()
    if base_vecs is None:
        return cosine, ("순위 밖", False)

    sims = _answer_sims_for(answer_word, ans_vec)
    if sims is None:
        return cosine, ("순위 밖", False)

    idx_in = model_loader.word_index_in_base(input_word)
    if idx_in is None:
        return cosine, ("순위 밖", False)

    my_sim = sims[idx_in]
    greater = sims > my_sim
    idx_ans = model_loader.word_index_in_base(answer_word)
    if idx_ans is not None:
        greater[idx_ans] = False

    rank_val = int(greater.sum()) + 1
    rank: int | str = rank_val if rank_val <= 500 else "순위 밖"
    return cosine, (rank, True)


def compute_rank(
    input_word: str,
    answer_word: str,
) -> tuple[int | str, bool]:
    """Determine the rank of *input_word* among all cached BaseWords.

    Returns:
        rank: int (1–500), or "순위 밖" if outside top-500
        base_word_exists: True if the word was found in the cached BaseWord list
    """
    _, r = compute_similarity_and_rank(input_word, answer_word)
    return r
