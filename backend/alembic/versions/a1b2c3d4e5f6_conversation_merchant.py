"""conversation 关联商家

Revision ID: a1b2c3d4e5f6
Revises: daf827a72948
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "daf827a72948"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("merchant_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_conversations_merchant", "conversations", "merchants", ["merchant_id"], ["id"])
    op.execute("UPDATE conversations SET merchant_id = (SELECT min(id) FROM merchants) WHERE merchant_id IS NULL")


def downgrade() -> None:
    op.drop_constraint("fk_conversations_merchant", "conversations", type_="foreignkey")
    op.drop_column("conversations", "merchant_id")
