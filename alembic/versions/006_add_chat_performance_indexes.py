"""Add performance indexes for chat queries.

Revision ID: 006
Revises: 005
Create Date: 2026-05-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Composite index for thread queries (email + is_deleted + created_at)
    op.create_index(
        'ix_chat_thread_lookup',
        'chat_messages',
        ['email', 'is_deleted', 'created_at'],
    )
    # Index for unread count queries
    op.create_index(
        'ix_chat_unread',
        'chat_messages',
        ['email', 'sender', 'is_read', 'is_deleted'],
    )
    # Index for contact messages lookup
    op.create_index(
        'ix_contact_is_deleted',
        'contact_messages',
        ['is_deleted', 'created_at'],
    )
    print("✅ Added chat performance indexes")


def downgrade():
    op.drop_index('ix_chat_thread_lookup', 'chat_messages')
    op.drop_index('ix_chat_unread', 'chat_messages')
    op.drop_index('ix_contact_is_deleted', 'contact_messages')
    print("✅ Removed chat performance indexes")
