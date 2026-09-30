"""мотивация 2.0 (2/4): отметки рефлексии в xp_events, соответствие старых достижений новым — expand

Старые достижения не удаляются. Тем, кто получил «серию 7 дней» / «серию 30 дней», дополнительно
выдаются уровни «Постоянства» (серия ≥ 7 дней — это ≥ 7 дней с дневником) с прежней датой получения.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

# старый код → коды категории, которые он подтверждает
MAPPING = {
    "streak_7": ("consistency_1",),
    "streak_30": ("consistency_1", "consistency_2"),
}


def upgrade() -> None:
    op.add_column("xp_events", sa.Column("marks", sa.String(32), nullable=True))
    conn = op.get_bind()
    achievements = sa.table(
        "achievements",
        sa.column("owner_id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("earned_on", sa.Date),
        sa.column("created_at", sa.DateTime),
    )
    rows = conn.execute(sa.select(achievements)).all()  # типы колонок → даты, а не строки
    have = {(r.owner_id, r.code) for r in rows}
    new: list[dict[str, object]] = []
    for row in rows:
        for code in MAPPING.get(row.code, ()):
            if (row.owner_id, code) not in have:
                have.add((row.owner_id, code))
                new.append(
                    {
                        "owner_id": row.owner_id,
                        "code": code,
                        "earned_on": row.earned_on,
                        "created_at": row.created_at,
                    }
                )
    if new:
        op.bulk_insert(achievements, new)


def downgrade() -> None:
    conn = op.get_bind()
    codes = sorted({c for mapped in MAPPING.values() for c in mapped})
    conn.execute(
        sa.text("DELETE FROM achievements WHERE code IN :codes").bindparams(
            sa.bindparam("codes", value=codes, expanding=True)
        )
    )
    op.drop_column("xp_events", "marks")
