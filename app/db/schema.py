"""Production schema guard.

Alembic is still useful for planned migrations, but this app is deployed on
serverless infrastructure where an older MySQL database may already exist.
This module performs small, non-destructive repairs so the ORM can query the
actual production table names and columns.
"""
import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.database import Base

logger = logging.getLogger(__name__)


PROJECT_COLUMNS = {
    "unique_id": "VARCHAR(36) NULL",
    "project_name": "VARCHAR(255) NOT NULL DEFAULT ''",
    "sub_category": "VARCHAR(100) NULL",
    "access_type": "ENUM('FREE','PAID','BOTH') NOT NULL DEFAULT 'FREE'",
    "details": "TEXT NULL",
    "subdetails": "TEXT NULL",
    "guide": "TEXT NULL",
    "source": "VARCHAR(255) NULL",
    "link": "VARCHAR(500) NULL",
    "image": "VARCHAR(500) NULL",
    "implementation": "LONGTEXT NULL",
    "approval_status": "ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING'",
    "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
    "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
}

LEGACY_PROJECT_COLUMNS = {
    "unique_id": ["uniqueId"],
    "project_name": ["projectName", "name", "title"],
    "sub_category": ["subCategory"],
    "access_type": ["accessType"],
    "approval_status": ["approvalStatus", "status"],
}

INDEXES = {
    "ix_projects_approval_status": ("alldata", "approval_status"),
    "ix_projects_access_type": ("alldata", "access_type"),
    "ix_projects_is_deleted": ("alldata", "is_deleted"),
    "ix_projects_name": ("alldata", "project_name"),
    "ix_projects_unique_id": ("alldata", "unique_id"),
    "ix_projects_created_at": ("alldata", "created_at"),
    "ix_chat_thread_lookup": ("chat_messages", "email, is_deleted, created_at"),
    "ix_chat_unread": ("chat_messages", "email, sender, is_read, is_deleted"),
    "ix_contact_is_deleted": ("contact_messages", "is_deleted, created_at"),
}


def ensure_database_schema(engine: Engine) -> None:
    """Create missing tables/columns needed by the current application."""
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        return

    if engine.dialect.name not in {"mysql", "mariadb"}:
        Base.metadata.create_all(bind=engine)
        return

    with engine.begin() as conn:
        _adopt_legacy_projects_table(conn)
        Base.metadata.create_all(bind=conn)
        _ensure_project_columns(conn)
        _ensure_mysql_enums(conn)
        _ensure_indexes(conn)


def _columns(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _adopt_legacy_projects_table(conn) -> None:
    inspector = inspect(conn)
    if inspector.has_table("projects") and not inspector.has_table("alldata"):
        logger.warning("Renaming legacy projects table to alldata")
        conn.execute(text("ALTER TABLE projects RENAME TO alldata"))


def _ensure_project_columns(conn) -> None:
    existing = _columns(conn, "alldata")
    if not existing:
        return

    for column_name, column_type in PROJECT_COLUMNS.items():
        if column_name not in existing:
            logger.warning("Adding missing production column alldata.%s", column_name)
            conn.execute(text(f"ALTER TABLE alldata ADD COLUMN {column_name} {column_type}"))
            existing.add(column_name)

    refreshed = _columns(conn, "alldata")
    for current_column, legacy_columns in LEGACY_PROJECT_COLUMNS.items():
        for legacy_column in legacy_columns:
            if legacy_column in refreshed:
                conn.execute(
                    text(
                        f"UPDATE alldata SET {current_column} = {legacy_column} "
                        f"WHERE ({current_column} IS NULL OR {current_column} = '') "
                        f"AND {legacy_column} IS NOT NULL"
                    )
                )
                break

    if "unique_id" in refreshed:
        conn.execute(
            text(
                "UPDATE alldata SET unique_id = UUID() "
                "WHERE unique_id IS NULL OR unique_id = ''"
            )
        )


def _ensure_mysql_enums(conn) -> None:
    conn.execute(
        text(
            "ALTER TABLE alldata MODIFY COLUMN access_type "
            "ENUM('FREE','PAID','BOTH') NOT NULL DEFAULT 'FREE'"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE alldata MODIFY COLUMN approval_status "
            "ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING'"
        )
    )


def _ensure_indexes(conn) -> None:
    for index_name, (table_name, columns) in INDEXES.items():
        table_indexes = {
            row[2]
            for row in conn.execute(text(f"SHOW INDEX FROM {table_name}")).fetchall()
        }
        if index_name in table_indexes:
            continue

        logger.info("Creating missing index %s on %s", index_name, table_name)
        conn.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({columns})"))
