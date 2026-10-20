"""Index the foreign keys that pages filter and join on.

Postgres does not index foreign keys on its own, so these lookups scanned
whole tables and would slow every page as data grows.
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

INDEXES = [
    ("expenses", "group_id"),
    ("expenses", "paid_by"),
    ("expense_splits", "expense_id"),
    ("expense_splits", "user_id"),
    ("settlements", "group_id"),
    ("memberships", "group_id"),
    ("friendships", "addressee_id"),
    ("group_invitations", "invited_user_id"),
]


def upgrade():
    for table, column in INDEXES:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table, column in INDEXES:
        op.drop_index(f"ix_{table}_{column}", table_name=table)
