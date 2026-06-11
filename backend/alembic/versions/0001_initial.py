"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-06-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("phone_number", sa.String(20), nullable=False, unique=True),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_phone_number", "users", ["phone_number"])

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("expired_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, default=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_otp_codes_phone_number", "otp_codes", ["phone_number"])

    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token", sa.String(1024), nullable=False, unique=True),
        sa.Column("expired_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("invite_token", sa.String(64), nullable=False, unique=True),
        sa.Column("max_members", sa.Integer(), nullable=False, default=20),
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False
        ),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_group"),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False
        ),
        sa.Column(
            "paid_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, default="USD"),
        sa.Column(
            "split_type",
            sa.Enum("EQUAL", "CUSTOM", name="splittype"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
    )

    op.create_table(
        "expense_splits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "expense_id",
            sa.String(36),
            sa.ForeignKey("expenses.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
    )

    op.create_table(
        "settlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False
        ),
        sa.Column(
            "from_user", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "to_user", sa.String(36), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, default=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settlements")
    op.drop_table("expense_splits")
    op.drop_table("expenses")
    op.drop_table("memberships")
    op.drop_table("groups")
    op.drop_table("token_blacklist")
    op.drop_index("ix_otp_codes_phone_number", table_name="otp_codes")
    op.drop_table("otp_codes")
    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_table("users")
