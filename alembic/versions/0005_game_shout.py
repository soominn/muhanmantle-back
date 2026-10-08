"""global shout counts, one row per session and word

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _unique_guess_words(raw: object) -> list[str]:
    """Words already stored on a session. The same word counts once."""
    if raw is None:
        return []
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        if not raw:
            return []
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return []

    seen: set[str] = set()
    words: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        word = item.get("word")
        if not isinstance(word, str):
            continue
        word = word.strip()
        if not word or word in seen or len(word) > 255:
            continue
        seen.add(word)
        words.append(word)
    return words


def upgrade() -> None:
    op.create_table(
        "game_shout",
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("word", "session_id"),
    )

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, guesses FROM game_session")).mappings()
    payload: list[dict[str, str]] = []
    for row in rows:
        for word in _unique_guess_words(row["guesses"]):
            payload.append({"word": word, "session_id": row["id"]})
    if payload:
        bind.execute(
            sa.text(
                "INSERT INTO game_shout (word, session_id) "
                "VALUES (:word, :session_id)"
            ),
            payload,
        )


def downgrade() -> None:
    op.drop_table("game_shout")
