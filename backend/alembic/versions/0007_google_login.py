"""Google sign-in: link a Google account to a user; phone becomes optional."""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("phone_number", existing_type=sa.String(20), nullable=True)
        batch.add_column(sa.Column("google_sub", sa.String(255), nullable=True))
        batch.add_column(sa.Column("email", sa.String(255), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade():
    op.drop_index("ix_users_google_sub", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email")
        batch.drop_column("google_sub")
        batch.alter_column("phone_number", existing_type=sa.String(20), nullable=False)
