"""webhooks
Revision ID: c84af5f906e3
Revises: af49c0e1b672
"""
from alembic import op
import sqlalchemy as sa

revision = "c84af5f906e3"
down_revision = "af49c0e1b672"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("webhook", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("url", sa.String(), nullable=False), sa.Column("events", sa.String(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))

def downgrade():
    op.drop_table("webhook")
