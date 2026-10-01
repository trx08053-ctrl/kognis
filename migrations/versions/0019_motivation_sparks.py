"""Мотивация 2.0 (4/4): искры — expand, две новые таблицы

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spark_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ref", sa.String(64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "kind", "ref", name="uq_spark_events_owner_kind_ref"),
    )
    op.create_index("ix_spark_events_owner_id", "spark_events", ["owner_id"])
    op.create_table(
        "spark_purchases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("item", sa.String(32), nullable=False),
        sa.Column("ref", sa.String(64), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "item", "ref", name="uq_spark_purchases_owner_item_ref"),
    )
    op.create_index("ix_spark_purchases_owner_id", "spark_purchases", ["owner_id"])


def downgrade() -> None:
    op.drop_table("spark_purchases")
    op.drop_table("spark_events")
