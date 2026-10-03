"""
Pytest fixtures.

The 3 GB FastText model is not available during CI/testing, so we:
  1. Patch model_loader.load_model to a no-op before any app import
  2. Patch model_loader._model to a small deterministic MagicMock
  3. Override get_db to use an in-memory SQLite database
"""

import os

# Force FastText mock path; a developer .env with sentence_transformer must not break tests
os.environ["SIMILARITY_BACKEND"] = "fasttext"

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Mock word model ──────────────────────────────────────────────────────────
# Must happen BEFORE any app code imports model_loader.

TEST_VOCAB: dict[str, int] = {"사과": 0, "바나나": 1, "오렌지": 2, "포도": 3}
TEST_WORDS = list(TEST_VOCAB.keys())
_N = len(TEST_VOCAB)

_rng = np.random.default_rng(42)
_raw = _rng.standard_normal((_N, 300)).astype(np.float32)
TEST_NORM_VECS = _raw / (np.linalg.norm(_raw, axis=1, keepdims=True) + 1e-12)

_mock_kv = MagicMock()
_mock_kv.key_to_index = TEST_VOCAB
_mock_kv.get_vector.side_effect = lambda w: TEST_NORM_VECS[TEST_VOCAB[w]].copy()

import app.services.model_loader as _ml  # noqa: E402

patch.object(_ml, "_similarity_backend", "fasttext").start()
patch.object(_ml, "_model", _mock_kv).start()
patch.object(_ml, "load_model", return_value=None).start()

# ── App / DB imports (after patching) ────────────────────────────────────────
from app.db.base import Base           # noqa: E402
from app.db.session import get_db      # noqa: E402
from app.main import app               # noqa: E402
from app.models.answer_word import AnswerWord  # noqa: F401, E402
from app.models.base_word import BaseWord  # noqa: F401, E402
from app.models.game_session import GameSession  # noqa: F401, E402
from app.models.game_shout import GameShout  # noqa: F401, E402

# ── In-memory SQLite DB ──────────────────────────────────────────────────────
# StaticPool forces all sessions to share one physical connection, so tables
# created by create_all() are visible to every session in the same test.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_state():
    """Fresh tables + clean word cache before every test."""
    Base.metadata.create_all(bind=_engine)
    _ml.build_baseword_matrix(TEST_WORDS, force=True)
    yield
    Base.metadata.drop_all(bind=_engine)
    _ml.mark_dirty()


@pytest.fixture
def db():
    session = _TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
