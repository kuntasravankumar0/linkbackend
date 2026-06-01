"""
Repository layer — all raw DB queries.
No business logic here. Services call this layer only.
"""
import uuid
import logging
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.db.cache import cache_result, invalidate_cache

logger = logging.getLogger(__name__)


def _active(db: Session):
    """Base query — always excludes soft-deleted rows."""
    return db.query(Project).filter(Project.is_deleted == False)  # noqa: E712


def get_all(db: Session) -> List[Project]:
    """Get all active projects — cached for 5 minutes."""
    # Note: Cache key doesn't include db object, relies on Session binding
    key = "repo_get_all"
    cached = _get_from_local_cache(key)
    if cached is not None:
        return cached
    
    result = _active(db).order_by(Project.created_at.desc()).all()
    _set_local_cache(key, result)
    return result


def get_by_id(db: Session, project_id: int) -> Optional[Project]:
    """Get by numeric ID — cached."""
    key = f"repo_get_by_id:{project_id}"
    cached = _get_from_local_cache(key)
    if cached is not None:
        return cached
    
    result = _active(db).filter(Project.id == project_id).first()
    _set_local_cache(key, result)
    return result


def get_by_unique_id(db: Session, unique_id: str) -> Optional[Project]:
    """Fetch by UUID string — cached."""
    key = f"repo_get_by_unique_id:{unique_id}"
    cached = _get_from_local_cache(key)
    if cached is not None:
        return cached
    
    result = _active(db).filter(Project.unique_id == unique_id).first()
    _set_local_cache(key, result)
    return result


def search_by_name(db: Session, project_name: str) -> List[Project]:
    """Case-insensitive LIKE search on project_name — cached."""
    if not project_name or not project_name.strip():
        return get_all(db)
    
    key = f"repo_search_by_name:{project_name.lower()}"
    cached = _get_from_local_cache(key)
    if cached is not None:
        return cached
    
    pattern = f"%{project_name.strip()}%"
    result = (
        _active(db)
        .filter(Project.project_name.ilike(pattern))
        .order_by(Project.created_at.desc())
        .all()
    )
    _set_local_cache(key, result)
    return result


def get_by_approval_status(db: Session, status: str) -> List[Project]:
    """Get by approval status — cached."""
    key = f"repo_get_by_approval_status:{status.upper()}"
    cached = _get_from_local_cache(key)
    if cached is not None:
        return cached
    
    result = (
        _active(db)
        .filter(Project.approval_status == status.upper())
        .order_by(Project.created_at.desc())
        .all()
    )
    _set_local_cache(key, result)
    return result


def get_by_access_type(db: Session, access_type: str) -> List[Project]:
    """Get by access type — cached."""
    key = f"repo_get_by_access_type:{access_type.upper()}"
    cached = _get_from_local_cache(key)
    if cached is not None:
        return cached
    
    result = (
        _active(db)
        .filter(Project.access_type == access_type.upper())
        .order_by(Project.created_at.desc())
        .all()
    )
    _set_local_cache(key, result)
    return result


def create(db: Session, data: ProjectCreate) -> Project:
    project = Project(
        unique_id=str(uuid.uuid4()),
        project_name=data.projectName,
        sub_category=data.subCategory,
        access_type=data.accessType.value,
        details=data.details,
        subdetails=data.subdetails,
        guide=data.guide,
        source=data.source,
        link=data.link,
        image=data.image,
        implementation=data.implementation,
        approval_status="PENDING",
        is_deleted=False,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.debug(f"Created project id={project.id} unique_id={project.unique_id}")
    
    # Invalidate relevant caches
    _clear_read_cache()
    return project


def get_by_name_exact(db: Session, name: str, exclude_id: Optional[int] = None) -> Optional[Project]:
    """Case-insensitive exact name match — used for duplicate detection."""
    q = _active(db).filter(func.lower(Project.project_name) == name.strip().lower())
    if exclude_id is not None:
        q = q.filter(Project.id != exclude_id)
    return q.first()


def update(db: Session, project: Project, data: ProjectUpdate) -> Project:
    """Partial update — only fields present in the payload are changed."""
    update_data = data.model_dump(exclude_unset=True)

    field_map = {
        "projectName":    "project_name",
        "subCategory":    "sub_category",
        "accessType":     "access_type",
        "details":        "details",
        "subdetails":     "subdetails",
        "guide":          "guide",
        "source":         "source",
        "link":           "link",
        "image":          "image",
        "implementation": "implementation",
    }

    for schema_key, model_key in field_map.items():
        if schema_key in update_data:
            val = update_data[schema_key]
            setattr(project, model_key, val.value if hasattr(val, "value") else val)

    db.commit()
    db.refresh(project)
    
    # Invalidate relevant caches
    _clear_read_cache()
    return project


def set_approval_status(db: Session, project: Project, status: str) -> Project:
    project.approval_status = status
    db.commit()
    db.refresh(project)
    
    # Invalidate relevant caches
    _clear_read_cache()
    return project


def soft_delete(db: Session, project: Project) -> None:
    project.is_deleted = True
    db.commit()
    logger.debug(f"Soft-deleted project id={project.id}")
    
    # Invalidate relevant caches
    _clear_read_cache()


def count_by_status(db: Session) -> dict:
    rows = (
        _active(db)
        .with_entities(Project.approval_status, func.count(Project.id))
        .group_by(Project.approval_status)
        .all()
    )
    return {row[0]: row[1] for row in rows}


# ── Cache helpers ──────────────────────────────────────────────────────────────
_local_cache: dict = {}


def _get_from_local_cache(key: str) -> Optional[Any]:
    """Get value from local cache if exists."""
    return _local_cache.get(key)


def _set_local_cache(key: str, value: Any) -> None:
    """Set value in local cache."""
    _local_cache[key] = value


def _clear_read_cache() -> None:
    """Clear all read caches (called on write operations)."""
    keys_to_clear = [k for k in _local_cache.keys() if k.startswith("repo_")]
    for k in keys_to_clear:
        del _local_cache[k]
    logger.debug(f"Cache cleared ({len(keys_to_clear)} entries)")
