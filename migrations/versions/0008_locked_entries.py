"""записи «под замком»: шифртекст, nonce, хэш пароля замка, версия формата

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("lock_cipher", sa.LargeBinary(), nullable=True))
    op.add_column("entries", sa.Column("lock_nonce", sa.LargeBinary(), nullable=True))
    op.add_column("entries", sa.Column("lock_hash", sa.String(255), nullable=True))
    op.add_column("entries", sa.Column("lock_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("entries", "lock_version")
    op.drop_column("entries", "lock_hash")
    op.drop_column("entries", "lock_nonce")
    op.drop_column("entries", "lock_cipher")
