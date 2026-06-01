"""
SQLAlchemy ORM model for the projects table.
Table name: alldata (already created in Aiven MySQL)
"""
import uuid
from sqlalchemy import (
    Column, Integer, String, Text,
    Enum as SAEnum, DateTime, Boolean, Index,
)
from app.db.database import Base
from app.db.time import utc_now_naive


class Project(Base):
    __tablename__ = "alldata"

    # ── Primary key ────────────────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # ── Unique identifier (UUID) shown in admin table ──────────────────────────
    unique_id = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    # ── Core fields ────────────────────────────────────────────────────────────
    project_name  = Column(String(255), nullable=False)
    sub_category  = Column(String(100), nullable=True)

    access_type = Column(
        SAEnum("FREE", "PAID", "BOTH", name="access_type_enum"),
        nullable=False,
        default="FREE",
    )

    details        = Column(Text,     nullable=True)
    subdetails     = Column(Text,     nullable=True)
    guide          = Column(Text,     nullable=True)
    source         = Column(String(255), nullable=True)
    link           = Column(String(500), nullable=True)
    image          = Column(String(500), nullable=True)
    implementation = Column(Text, nullable=True)

    # ── Approval workflow ──────────────────────────────────────────────────────
    approval_status = Column(
        SAEnum("PENDING", "APPROVED", "REJECTED", name="approval_status_enum"),
        nullable=False,
        default="PENDING",
    )

    # ── Soft delete ────────────────────────────────────────────────────────────
    is_deleted = Column(Boolean, default=False, nullable=False)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_projects_approval_status", "approval_status"),
        Index("ix_projects_access_type", "access_type"),
        Index("ix_projects_is_deleted", "is_deleted"),
        Index("ix_projects_name", "project_name"),
        Index("ix_projects_unique_id", "unique_id"),
        Index("ix_projects_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Project id={self.id} name='{self.project_name}' status={self.approval_status}>"
