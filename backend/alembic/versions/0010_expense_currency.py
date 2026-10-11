"""Lock an exchange rate and USD value onto each expense and split."""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    # Every expense so far was entered in USD.
    with op.batch_alter_table("expenses") as batch:
        batch.add_column(sa.Column("fx_rate", sa.Numeric(18, 6), nullable=False, server_default="1"))
        batch.add_column(sa.Column("amount_usd", sa.Numeric(12, 2), nullable=True))
    op.execute("UPDATE expenses SET amount_usd = amount")
    with op.batch_alter_table("expenses") as batch:
        batch.alter_column("amount_usd", existing_type=sa.Numeric(12, 2), nullable=False)

    with op.batch_alter_table("expense_splits") as batch:
        batch.add_column(sa.Column("amount_usd", sa.Numeric(12, 2), nullable=True))
    op.execute("UPDATE expense_splits SET amount_usd = amount")
    with op.batch_alter_table("expense_splits") as batch:
        batch.alter_column("amount_usd", existing_type=sa.Numeric(12, 2), nullable=False)


def downgrade():
    with op.batch_alter_table("expense_splits") as batch:
        batch.drop_column("amount_usd")
    with op.batch_alter_table("expenses") as batch:
        batch.drop_column("amount_usd")
        batch.drop_column("fx_rate")
