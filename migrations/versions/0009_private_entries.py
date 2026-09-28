"""приватные записи: конверт шифртекста, собранный в браузере

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("private_envelope", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("entries", "private_envelope")
