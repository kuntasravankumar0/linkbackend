"""Add BOTH to access_type enum

Revision ID: 002
Revises: 001
Create Date: 2026-05-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MySQL requires MODIFY COLUMN to change enum values
    op.execute(
        "ALTER TABLE alldata MODIFY COLUMN access_type "
        "ENUM('FREE','PAID','BOTH') NOT NULL DEFAULT 'FREE'"
    )


def downgrade() -> None:
    # Remove BOTH — existing BOTH rows will need manual cleanup first
    op.execute(
        "ALTER TABLE alldata MODIFY COLUMN access_type "
        "ENUM('FREE','PAID') NOT NULL DEFAULT 'FREE'"
    )
