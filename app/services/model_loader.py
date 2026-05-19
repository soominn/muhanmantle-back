"""
Word-embedding backend: FastText (gensim) or sentence-transformers.

BaseWord rows are projected to L2-normalised vectors; similarity is cosine
(dot product). Top-k ranking uses the same argpartition path for both backends.

ChromaDB is not required: optional on-disk cache (see Settings.embedding_cache_dir)
speeds up ST rebuilds when the BaseWord list is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from gensim.models import KeyedVectors

# ── Backend + FastText singleton ─────────────────────────────────────────────

_similarity_backend: Literal["fasttext", "sentence_transformer"] = "fasttext"
_model: Optional[KeyedVectors] = None
_st_model: Optional[object] = None

# ── BaseWord similarity cache ────────────────────────────────────────────────

_base_words: list[str] = []
_base_vecs: Optional[np.ndarray] = None  # (N, D), L2-normalised float32
_base_word_set: set[str] = set()  # mirrors _base_words for O(1) membership on append
_base_word_to_idx: dict[str, int] = {}  # same order as _base_words; avoids rebuilding per guess
_base_matrix_gen: int = 0  # bumps when BaseWord matrix rows change (cache invalidation helper)
_base_dirty: bool = True
_base_lock: threading.RLock = threading.RLock()


def get_similarity_backend() -> Literal["fasttext", "sentence_transformer"]:
    return _similarity_backend


def initialize() -> None:
    """Load ML models once at app startup (see app.main lifespan)."""
    global _similarity_backend, _model, _st_model

    from app.core.config import settings

    _similarity_backend = settings.similarity_backend

    if settings.similarity_backend == "sentence_transformer":
        _model = None
        from sentence_transformers import SentenceTransformer

        kwargs: dict = {}
        if settings.sentence_transformer_device:
            kwargs["device"] = settings.sentence_transformer_device

        _st_model = SentenceTransformer(settings.sentence_transformer_model, **kwargs)
    else:
        _st_model = None
        load_model(settings.vec_file, settings.kv_file)


def load_model(vec_file: str, kv_file: str) -> None:
    """Load KeyedVectors. Prefers cached .kv; falls back to .vec."""
    global _model
    if os.path.exists(kv_file):
        _model = KeyedVectors.load(kv_file)
    else:
        _model = KeyedVectors.load_word2vec_format(
            vec_file, binary=False, unicode_errors="ignore"
        )
        _model.save(kv_file)


def get_model() -> KeyedVectors:
    if _similarity_backend == "sentence_transformer":
        raise RuntimeError("FastText model is not loaded in sentence_transformer backend.")
    if _model is None:
        raise RuntimeError("Word model is not loaded — check startup logs.")
    return _model


def word_in_model(word: str) -> bool:
    """Whether *word* is accepted for similarity scoring (backend-specific)."""
    w = word.strip()
    if not w:
        return False
    if _similarity_backend == "fasttext":
        return w in get_model().key_to_index
    # sentence-transformers: any non-empty token string can be embedded
    return len(w) <= 200


def needs_rebuild() -> bool:
    with _base_lock:
        return _base_dirty


def base_matrix_generation() -> int:
    """Monotonic counter incremented when the BaseWord matrix is rebuilt or appended to."""
    with _base_lock:
        return _base_matrix_gen


def word_index_in_base(word: str) -> Optional[int]:
    """Index of *word* in the cached BaseWord list, or None if absent."""
    w = (word or "").strip()
    if not w:
        return None
    with _base_lock:
        i = _base_word_to_idx.get(w)
        return int(i) if i is not None else None


def _st_words_fingerprint(words: list[str]) -> str:
    payload = json.dumps(words, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _st_cache_file(words: list[str]) -> Path:
    from app.core.config import settings

    safe = settings.sentence_transformer_model.replace("/", "__")
    d = settings.embedding_cache_dir / safe
    d.mkdir(parents=True, exist_ok=True)
    return d / f"baseword_{_st_words_fingerprint(words)}.npz"


def _try_load_st_cache(path: Path, expected_words: list[str]) -> Optional[tuple[list[str], np.ndarray]]:
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=True)
    words = data["words"].tolist()
    emb = np.asarray(data["emb"], dtype=np.float32)
    if words != expected_words:
        return None
    norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12
    return words, emb / norms


def _save_st_cache(path: Path, words: list[str], emb: np.ndarray) -> None:
    np.savez_compressed(
        path,
        words=np.asarray(words, dtype=object),
        emb=np.asarray(emb, dtype=np.float32),
    )


def _fasttext_rows_normalized(model: KeyedVectors, filtered: list[str]) -> np.ndarray:
    """Stack L2-normalised rows for *filtered* words (bulk read when available)."""
    if not filtered:
        d = int(getattr(model, "vector_size", 0) or 0)
        return np.zeros((0, d), dtype=np.float32)

    raw = getattr(model, "vectors", None)
    if isinstance(raw, np.ndarray):
        try:
            idx = np.fromiter(
                (model.key_to_index[w] for w in filtered),
                dtype=np.int64,
                count=len(filtered),
            )
            vecs = np.asarray(raw[idx], dtype=np.float32)
            if vecs.ndim == 1:
                vecs = vecs.reshape(1, -1)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
            return vecs / norms
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            pass

    vecs = np.vstack([model.get_vector(w) for w in filtered]).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    return vecs / norms


def build_baseword_matrix(words_from_db: list[str], force: bool = False) -> None:
    """Rebuild the normalised vector matrix from the supplied word list."""
    global _base_words, _base_vecs, _base_word_set, _base_word_to_idx, _base_matrix_gen, _base_dirty

    with _base_lock:
        if not force and not _base_dirty:
            return

        in_vocab = [w.strip() for w in words_from_db if w and str(w).strip()]
        if not in_vocab:
            _base_words = []
            _base_vecs = None
            _base_word_set = set()
            _base_word_to_idx = {}
            _base_matrix_gen += 1
            _base_dirty = False
            return

        if _similarity_backend == "fasttext":
            model = get_model()
            filtered = [w for w in in_vocab if w in model.key_to_index]
            if not filtered:
                _base_words = []
                _base_vecs = None
                _base_word_set = set()
                _base_word_to_idx = {}
                _base_matrix_gen += 1
                _base_dirty = False
                return
            _base_words = filtered
            _base_vecs = _fasttext_rows_normalized(model, filtered)
            _base_word_set = set(filtered)
            _base_word_to_idx = {w: i for i, w in enumerate(filtered)}
            _base_matrix_gen += 1
            _base_dirty = False
            return

        # ── sentence-transformers ───────────────────────────────────────────
        assert _st_model is not None
        cache_path = _st_cache_file(in_vocab)
        cached = _try_load_st_cache(cache_path, in_vocab)
        if cached is not None:
            _base_words, _base_vecs = cached
            _base_word_set = set(_base_words)
            _base_word_to_idx = {w: i for i, w in enumerate(_base_words)}
            _base_matrix_gen += 1
            _base_dirty = False
            return

        encode_bs = 256 if len(in_vocab) >= 4096 else 64
        emb = _st_model.encode(
            in_vocab,
            batch_size=encode_bs,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        emb = np.asarray(emb, dtype=np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12
        _base_words = in_vocab
        _base_vecs = emb / norms
        _base_word_set = set(in_vocab)
        _base_word_to_idx = {w: i for i, w in enumerate(in_vocab)}
        _base_matrix_gen += 1
        try:
            _save_st_cache(cache_path, in_vocab, emb)
        except OSError:
            # Cache is optional; continue in RAM-only mode
            pass
        _base_dirty = False


def append_base_word_to_cache(word: str) -> None:
    """After a new BaseWord row is committed, add one matrix row without rebuilding ~80k vectors."""
    global _base_words, _base_vecs, _base_word_set, _base_word_to_idx, _base_matrix_gen

    w = (word or "").strip()
    if not w:
        return

    with _base_lock:
        if _base_dirty or w in _base_word_set:
            return

        if _similarity_backend == "fasttext":
            model = get_model()
            if w not in model.key_to_index:
                return
            row = _fasttext_rows_normalized(model, [w])[0]
        else:
            assert _st_model is not None
            emb = _st_model.encode(
                [w],
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            row = np.asarray(emb[0], dtype=np.float32)
            row /= np.linalg.norm(row) + 1e-12

        row2 = row.reshape(1, -1).astype(np.float32, copy=False)
        if _base_vecs is None or len(_base_words) == 0:
            _base_words = [w]
            _base_word_set = {w}
            _base_word_to_idx = {w: 0}
            _base_vecs = row2
            _base_matrix_gen += 1
            return

        _base_words.append(w)
        _base_word_set.add(w)
        _base_word_to_idx[w] = len(_base_words) - 1
        _base_vecs = np.concatenate([_base_vecs, row2], axis=0)
        _base_matrix_gen += 1


def mark_dirty() -> None:
    global _base_dirty
    with _base_lock:
        _base_dirty = True


def get_cache() -> tuple[list[str], Optional[np.ndarray]]:
    with _base_lock:
        return _base_words, _base_vecs


def get_normalized_vector(word: str) -> Optional[np.ndarray]:
    w = word.strip()
    if not w:
        return None

    if _similarity_backend == "fasttext":
        model = get_model()
        if w not in model.key_to_index:
            return None
        v = model.get_vector(w).astype(np.float32)
        v /= np.linalg.norm(v) + 1e-12
        return v

    assert _st_model is not None
    v = _st_model.encode(
        [w],
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )[0].astype(np.float32)
    v /= np.linalg.norm(v) + 1e-12
    return v


def top_k_by_similarity(
    sims: np.ndarray,
    words: list[str],
    k: int = 500,
    exclude_word: Optional[str] = None,
) -> list[dict]:
    if sims.size == 0:
        return []

    k_eff = min(k + 1, sims.shape[0])
    idx = np.argpartition(-sims, kth=k_eff - 1)[:k_eff]
    idx = idx[np.argsort(-sims[idx])]

    results: list[dict] = []
    rank = 1
    for i in idx:
        w = words[i]
        if exclude_word is not None and w == exclude_word:
            continue
        results.append(
            {
                "word": w,
                "similarity_percentage": round(float(sims[i]) * 100, 2),
                "rank": rank,
            }
        )
        rank += 1
        if len(results) == k:
            break
    return results
