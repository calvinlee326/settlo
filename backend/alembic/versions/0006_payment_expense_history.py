"""Payment actors, reversal history, and expense revisions."""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("settlements") as batch:
        batch.add_column(sa.Column("recorded_by", sa.String(36), nullable=True))
        batch.add_column(sa.Column("reversed_by", sa.String(36), nullable=True))
        batch.add_column(sa.Column("reversed_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_settlement_recorded_by", "users", ["recorded_by"], ["id"])
        batch.create_foreign_key("fk_settlement_reversed_by", "users", ["reversed_by"], ["id"])
    op.create_table(
        "expense_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
    )
    op.create_index("ix_expense_revisions_expense_id", "expense_revisions", ["expense_id"])


def downgrade():
    op.drop_table("expense_revisions")
    with op.batch_alter_table("settlements") as batch:
        batch.drop_constraint("fk_settlement_recorded_by", type_="foreignkey")
        batch.drop_constraint("fk_settlement_reversed_by", type_="foreignkey")
        batch.drop_column("reversed_at")
        batch.drop_column("reversed_by")
        batch.drop_column("recorded_by")
