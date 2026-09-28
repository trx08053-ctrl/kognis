"""квесты, шаги квестов и ответы квизов-рефлексий

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=False),
        sa.Column("template_code", sa.String(32), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_quests_owner_id", "quests", ["owner_id"])
    op.create_table(
        "quest_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("quest_id", sa.Integer(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("done_on", sa.Date(), nullable=True),
        sa.UniqueConstraint("quest_id", "idx", name="uq_quest_steps_quest_idx"),
    )
    op.create_index("ix_quest_steps_quest_id", "quest_steps", ["quest_id"])
    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("quiz_code", sa.String(32), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_id", "quiz_code", "day", name="uq_quiz_answers_owner_quiz_day"),
    )
    op.create_index("ix_quiz_answers_owner_id", "quiz_answers", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_answers_owner_id", table_name="quiz_answers")
    op.drop_table("quiz_answers")
    op.drop_index("ix_quest_steps_quest_id", table_name="quest_steps")
    op.drop_table("quest_steps")
    op.drop_index("ix_quests_owner_id", table_name="quests")
    op.drop_table("quests")
