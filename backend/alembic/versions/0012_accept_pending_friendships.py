"""Adding a friend by ID no longer needs approval: accept requests still waiting.

Downgrading cannot tell which friendships were pending, so they stay accepted.
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE friendships SET status = 'ACCEPTED', responded_at = CURRENT_TIMESTAMP"
        " WHERE status = 'PENDING'"
    )


def downgrade():
    pass
