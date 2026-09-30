"""мотивация 2.0 (1/4): настройки серии и восстановления — expand, две новые таблицы

Существующим пользователям (есть xp_events) — строка настроек с rules_from = дата миграции:
до неё действует прежнее правило заморозки, поэтому серия при переходе не уменьшается.

Revision ID: 0016
Revises: 0015
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings = op.create_table(
        "gameplay_settings",
        sa.Column("owner_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("weekend_days", sa.String(16), nullable=False),
        sa.Column("weekly_goal", sa.Integer(), nullable=False),
        sa.Column("rules_from", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("owner_id"),
    )
    op.create_table(
        "streak_recoveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("after_day", sa.Date(), nullable=False),
        sa.Column("broken_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "after_day", name="uq_streak_recoveries_owner_after"),
    )
    conn = op.get_bind()
    owners = conn.execute(sa.text("SELECT DISTINCT owner_id FROM xp_events")).scalars().all()
    today = datetime.now(UTC).date()
    if owners:
        op.bulk_insert(
            settings,
            [
                {"owner_id": o, "weekend_days": "", "weekly_goal": 3, "rules_from": today}
                for o in owners
            ],
        )


def downgrade() -> None:
    op.drop_table("streak_recoveries")
    op.drop_table("gameplay_settings")
