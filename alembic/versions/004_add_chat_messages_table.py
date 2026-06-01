"""Add chat_messages table

Revision ID: 004
Revises: 003
Create Date: 2026-05-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id",         sa.Integer(),    autoincrement=True, nullable=False),
        sa.Column("email",      sa.String(255),  nullable=False),
        sa.Column("name",       sa.String(255),  nullable=True),
        sa.Column("sender",     sa.String(10),   nullable=False),   # 'user' or 'admin'
        sa.Column("message",    sa.Text(),        nullable=False),
        sa.Column("is_read",    sa.Boolean(),    nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(),    nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_id",      "chat_messages", ["id"])
    op.create_index("ix_chat_messages_email",   "chat_messages", ["email"])
    op.create_index("ix_chat_messages_sender",  "chat_messages", ["sender"])
    op.create_index("ix_chat_messages_is_read", "chat_messages", ["is_read"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_is_read", table_name="chat_messages")
    op.drop_index("ix_chat_messages_sender",  table_name="chat_messages")
    op.drop_index("ix_chat_messages_email",   table_name="chat_messages")
    op.drop_index("ix_chat_messages_id",      table_name="chat_messages")
    op.drop_table("chat_messages")
