"""run lifecycle statuses

Revision ID: af49c0e1b672
Revises: 90202e1e68ac
"""
from alembic import op

revision = "af49c0e1b672"
down_revision = "90202e1e68ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add lifecycle enum values where the database enforces native enums."""
    if op.get_bind().dialect.name == "postgresql":
        for value in ("PAUSED", "CANCELLED"):
            op.execute(f"ALTER TYPE runstatus ADD VALUE IF NOT EXISTS '{value}'")
        op.execute("ALTER TYPE stepstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    """PostgreSQL enum values cannot be removed without rebuilding the type."""
    pass
