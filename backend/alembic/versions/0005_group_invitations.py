"""group invitations table

Revision ID: 0005
Revises: 0004
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("invited_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACCEPTED", name="groupinvitationstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("group_id", "invited_user_id", name="uq_group_invitation"),
    )


def downgrade() -> None:
    op.drop_table("group_invitations")
