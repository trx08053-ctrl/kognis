"""индекс записей по (владелец, дата, id): постраничная выдача и отбор по периоду

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_entries_owner_date_id", "entries", ["owner_id", "entry_date", "id"])


def downgrade() -> None:
    op.drop_index("ix_entries_owner_date_id", table_name="entries")
