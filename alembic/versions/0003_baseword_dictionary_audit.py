"""baseword verification metadata and candidate table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simword_baseword",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "simword_baseword",
        sa.Column("verification_source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "simword_baseword",
        sa.Column("verification_note", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "simword_baseword_candidate",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("word", sa.String(length=100), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "first_seen_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("word"),
    )


def downgrade() -> None:
    op.drop_table("simword_baseword_candidate")
    op.drop_column("simword_baseword", "verification_note")
    op.drop_column("simword_baseword", "verification_source")
    op.drop_column("simword_baseword", "is_verified")
