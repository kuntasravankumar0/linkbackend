"""Add performance indexes for search and lookups.

Revision ID: 005
Revises: 004
Create Date: 2026-05-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Add indexes for frequently queried columns
    op.create_index('ix_projects_name', 'alldata', ['project_name'])
    op.create_index('ix_projects_unique_id', 'alldata', ['unique_id'])
    op.create_index('ix_projects_created_at', 'alldata', ['created_at'])
    print("✅ Added performance indexes: project_name, unique_id, created_at")


def downgrade():
    op.drop_index('ix_projects_name', 'alldata')
    op.drop_index('ix_projects_unique_id', 'alldata')
    op.drop_index('ix_projects_created_at', 'alldata')
    print("✅ Removed performance indexes")
