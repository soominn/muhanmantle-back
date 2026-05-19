"""Initial tables: simword_answerword, simword_baseword

Revision ID: 0001
Revises:
Create Date: 2026-04-24

Table names match Django's app_model convention so existing Django databases
can skip this migration and instead run: alembic stamp 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simword_answerword",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("answer_word", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "simword_baseword",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("base_word", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("simword_baseword")
    op.drop_table("simword_answerword")
