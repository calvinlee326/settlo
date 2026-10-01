"""Unique @ID per user so friends can find each other without a phone number."""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("handle", sa.String(30), nullable=True))
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)


def downgrade():
    op.drop_index("ix_users_handle", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("handle")
