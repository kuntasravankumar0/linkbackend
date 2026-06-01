"""
Service layer — all business logic lives here.
Repositories handle raw DB. Services handle rules, mapping, validation.
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
import app.repositories.project_repository as repo

logger = logging.getLogger(__name__)


def _to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,  # type: ignore[arg-type]
        uniqueId=project.unique_id,  # type: ignore[arg-type]
        projectName=project.project_name,  # type: ignore[arg-type]
        subCategory=project.sub_category,  # type: ignore[arg-type]
        accessType=project.access_type,  # type: ignore[arg-type]
        details=project.details,  # type: ignore[arg-type]
        subdetails=project.subdetails,  # type: ignore[arg-type]
        guide=project.guide,  # type: ignore[arg-type]
        source=project.source,  # type: ignore[arg-type]
        link=project.link,  # type: ignore[arg-type]
        image=project.image,  # type: ignore[arg-type]
        implementation=project.implementation,  # type: ignore[arg-type]
        approvalStatus=project.approval_status,  # type: ignore[arg-type]
    )


def _not_found(project_id):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": f"Project '{project_id}' not found.", "errors": None},
    )


def _duplicate_name_error(name: str):
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": f"A project named \"{name}\" already exists. Please use a unique name.",
            "errors": {"projectName": "Duplicate project name."},
        },
    )


# ── Read ───────────────────────────────────────────────────────────────────────

def get_all(db: Session) -> List[ProjectResponse]:
    return [_to_response(p) for p in repo.get_all(db)]


def get_by_id(db: Session, project_id: int) -> ProjectResponse:
    project = repo.get_by_id(db, project_id)
    if not project:
        _not_found(project_id)
    # project is now guaranteed not None
    return _to_response(project)


def get_by_unique_id(db: Session, unique_id: str) -> ProjectResponse:
    """Fetch a project by its UUID string."""
    project = repo.get_by_unique_id(db, unique_id)
    if not project:
        _not_found(unique_id)
    # project is now guaranteed not None
    return _to_response(project)  # type: ignore[arg-type]


def filter_projects(
    db: Session,
    access_type: Optional[str] = None,
    status: Optional[str] = None,
) -> List[ProjectResponse]:
    if status:
        projects = repo.get_by_approval_status(db, status)
    elif access_type:
        projects = repo.get_by_access_type(db, access_type)
    else:
        projects = repo.get_all(db)
    return [_to_response(p) for p in projects]


def search_projects(db: Session, project_name: str) -> List[ProjectResponse]:
    projects = repo.search_by_name(db, project_name)
    return [_to_response(p) for p in projects]


# ── Write ──────────────────────────────────────────────────────────────────────

def create_project(db: Session, data: ProjectCreate) -> ProjectResponse:
    """Create — rejects duplicate project names (case-insensitive)."""
    existing = repo.get_by_name_exact(db, data.projectName)
    if existing:
        _duplicate_name_error(data.projectName)
    project = repo.create(db, data)
    logger.info(f"Created project id={project.id} name='{project.project_name}'")
    return _to_response(project)


def update_project(db: Session, project_id: int, data: ProjectUpdate) -> ProjectResponse:
    """Update by numeric ID — rejects duplicate names (excluding self)."""
    project = repo.get_by_id(db, project_id)
    if not project:
        _not_found(project_id)
    # Duplicate name check — skip if name not being changed
    if data.projectName is not None:
        dup = repo.get_by_name_exact(db, data.projectName, exclude_id=project_id)
        if dup:
            _duplicate_name_error(data.projectName)
    updated = repo.update(db, project, data)
    logger.info(f"Updated project id={project_id}")
    return _to_response(updated)  # type: ignore[arg-type]


def update_project_by_uuid(db: Session, unique_id: str, data: ProjectUpdate) -> ProjectResponse:
    """Update by UUID string — same duplicate-name protection."""
    project = repo.get_by_unique_id(db, unique_id)
    if not project:
        _not_found(unique_id)
    if data.projectName is not None:
        dup = repo.get_by_name_exact(db, data.projectName, exclude_id=project.id)
        if dup:
            _duplicate_name_error(data.projectName)
    updated = repo.update(db, project, data)
    logger.info(f"Updated project uuid={unique_id}")
    return _to_response(updated)  # type: ignore[arg-type]


def approve_project(db: Session, project_id: int) -> ProjectResponse:
    project = repo.get_by_id(db, project_id)
    if not project:
        _not_found(project_id)
    updated = repo.set_approval_status(db, project, "APPROVED")
    logger.info(f"Approved project id={project_id}")
    return _to_response(updated)  # type: ignore[arg-type]


def reject_project(db: Session, project_id: int) -> ProjectResponse:
    project = repo.get_by_id(db, project_id)
    if not project:
        _not_found(project_id)
    updated = repo.set_approval_status(db, project, "REJECTED")
    logger.info(f"Rejected project id={project_id}")
    return _to_response(updated)  # type: ignore[arg-type]


def delete_project(db: Session, project_id: int) -> None:
    project = repo.get_by_id(db, project_id)
    if not project:
        _not_found(project_id)
    repo.soft_delete(db, project)
    logger.info(f"Soft-deleted project id={project_id}")
