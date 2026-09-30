"""мотивация 2.0 (3/4): спутник и открытки — expand, две новые таблицы

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companions",
        sa.Column("owner_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("appearance", sa.String(16), nullable=False),
        sa.Column("name", sa.String(24), nullable=False),
        sa.Column("address", sa.String(2), nullable=False),
        sa.Column("stage_seen", sa.Integer(), nullable=False),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id"),
    )
    op.create_table(
        "companion_postcards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("for_day", sa.Date(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "day", name="uq_companion_postcards_owner_day"),
    )
    op.create_index("ix_companion_postcards_owner_id", "companion_postcards", ["owner_id"])


def downgrade() -> None:
    op.drop_table("companion_postcards")
    op.drop_table("companions")
