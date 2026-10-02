"""Мотивация 2.0 (4/4): квест дня — expand, одна новая таблица

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_picks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("done_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "day", name="uq_daily_picks_owner_day"),
    )
    op.create_index("ix_daily_picks_owner_id", "daily_picks", ["owner_id"])


def downgrade() -> None:
    op.drop_table("daily_picks")
