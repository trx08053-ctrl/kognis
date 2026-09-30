"""память ИИ между разборами (analysis_memory): expand — новая таблица

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_memory",
        sa.Column("owner_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id"),
    )


def downgrade() -> None:
    op.drop_table("analysis_memory")
