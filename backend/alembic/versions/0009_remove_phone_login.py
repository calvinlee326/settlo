"""Phone login removed: drop OTP codes and erase phone numbers of Google-linked users.

Users who never linked Google keep their number so an admin can confirm who
they are before linking their Google account by hand. Erased numbers cannot be
restored by downgrading.
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE users SET phone_number = NULL WHERE google_sub IS NOT NULL")
    op.drop_index("ix_otp_codes_phone_number", table_name="otp_codes")
    op.drop_table("otp_codes")


def downgrade():
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
