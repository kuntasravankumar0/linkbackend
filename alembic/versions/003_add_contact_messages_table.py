"""Add contact_messages table

Revision ID: 003
Revises: 002
Create Date: 2026-05-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id",         sa.Integer(),     autoincrement=True, nullable=False),
        sa.Column("name",       sa.String(255),   nullable=False),
        sa.Column("email",      sa.String(255),   nullable=False),
        sa.Column("phone",      sa.String(30),    nullable=True),
        sa.Column("subject",    sa.String(255),   nullable=True),
        sa.Column("message",    sa.Text(),        nullable=False),
        sa.Column("is_read",    sa.Boolean(),     nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(),     nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_messages_id",       "contact_messages", ["id"])
    op.create_index("ix_contact_messages_is_read",  "contact_messages", ["is_read"])
    op.create_index("ix_contact_messages_email",    "contact_messages", ["email"])


def downgrade() -> None:
    op.drop_index("ix_contact_messages_email",   table_name="contact_messages")
    op.drop_index("ix_contact_messages_is_read", table_name="contact_messages")
    op.drop_index("ix_contact_messages_id",      table_name="contact_messages")
    op.drop_table("contact_messages")
