"""group settle + soft delete

Revision ID: 0002
Revises: 0001
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.add_column(sa.Column("settled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("settled_by", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("settled_by")
        batch_op.drop_column("settled_at")
