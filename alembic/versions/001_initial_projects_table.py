"""Initial projects table

Revision ID: 001
Revises:
Create Date: 2026-05-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("unique_id", sa.String(length=36), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("sub_category", sa.String(length=100), nullable=True),
        sa.Column(
            "access_type",
            sa.Enum("FREE", "PAID", name="access_type_enum"),
            nullable=False,
            server_default="FREE",
        ),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("subdetails", sa.Text(), nullable=True),
        sa.Column("guide", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("image", sa.String(length=500), nullable=True),
        sa.Column("implementation", mysql.LONGTEXT(), nullable=True),
        sa.Column(
            "approval_status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="approval_status_enum"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unique_id"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_approval_status", "projects", ["approval_status"])
    op.create_index("ix_projects_access_type", "projects", ["access_type"])
    op.create_index("ix_projects_is_deleted", "projects", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_projects_is_deleted", table_name="projects")
    op.drop_index("ix_projects_access_type", table_name="projects")
    op.drop_index("ix_projects_approval_status", table_name="projects")
    op.drop_index("ix_projects_id", table_name="projects")
    op.drop_table("projects")
