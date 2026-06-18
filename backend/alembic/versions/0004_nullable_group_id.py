"""make expense and settlement group_id nullable

Revision ID: 0004
Revises: 0003
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=True)
    with op.batch_alter_table("settlements", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    # Re-adds NOT NULL; fails if any direct (group_id IS NULL) expenses or
    # settlements exist. Delete or reassign those rows before downgrading.
    with op.batch_alter_table("settlements", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=False)
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=False)
