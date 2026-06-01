"""
Template routes.
Base prefix: /api/templates

Special feature:
  POST /api/templates with header  X-Admin-Key: SRAVAN@123
  → project is created AND immediately APPROVED (default approve).
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, status, Query, Header
from sqlalchemy.orm import Session

from app.auth.admin import is_admin_key, require_admin
from app.db.database import get_db
from app.schemas.project import (
    ProjectCreate, ProjectUpdate,
    ProjectResponse, ProjectListResponse,
)
import app.services.project_service as service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/templates", tags=["Templates"])

# SHA-256 of "SRAVAN@123" — admin key for default-approve



# ── GET /api/templates ─────────────────────────────────────────────────────────
@router.get("", response_model=ProjectListResponse, summary="Get all projects")
def get_all_projects(db: Session = Depends(get_db)):
    projects = service.get_all(db)
    logger.debug(f"get_all → {len(projects)} projects")
    return ProjectListResponse(content=projects)


# ── GET /api/templates/search?projectName= ────────────────────────────────────
@router.get("/search", response_model=ProjectListResponse, summary="Search by name")
def search_projects(
    projectName: str = Query(default="", description="Partial name to search"),
    db: Session = Depends(get_db),
):
    projects = service.search_projects(db, projectName)
    logger.debug(f"search '{projectName}' → {len(projects)} results")
    return ProjectListResponse(content=projects)


# ── GET /api/templates/filter?accessType=&status= ─────────────────────────────
@router.get("/filter", response_model=ProjectListResponse, summary="Filter projects")
def filter_projects(
    accessType: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    projects = service.filter_projects(db, access_type=accessType, status=status)
    logger.debug(f"filter accessType={accessType} status={status} → {len(projects)} results")
    return ProjectListResponse(content=projects)


# ── GET /api/templates/by-uuid/:uniqueId ──────────────────────────────────────
@router.get(
    "/by-uuid/{unique_id}",
    response_model=ProjectResponse,
    summary="Get project by UUID",
    description="Fetch a single project using its uniqueId (UUID string).",
)
def get_project_by_uuid(unique_id: str, db: Session = Depends(get_db)):
    return service.get_by_unique_id(db, unique_id)


# ── PUT /api/templates/by-uuid/:uniqueId ──────────────────────────────────────
@router.put(
    "/by-uuid/{unique_id}",
    response_model=ProjectResponse,
    summary="Update project by UUID",
    description="Partial update using uniqueId. Rejects duplicate project names.",
)
def update_project_by_uuid(
    unique_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    project = service.update_project_by_uuid(db, unique_id, data)
    logger.info(f"Updated project uuid={unique_id}")
    return project


# ── GET /api/templates/:id ────────────────────────────────────────────────────
@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
def get_project(project_id: int, db: Session = Depends(get_db)):
    return service.get_by_id(db, project_id)


# ── POST /api/templates ───────────────────────────────────────────────────────
@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new project",
    description=(
        "New projects default to PENDING.\n"
        "Pass header `X-Admin-Key: SRAVAN@123` to auto-approve on creation.\n"
        "Returns 409 if name already exists."
    ),
)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    project = service.create_project(db, data)
    # Default-approve if valid admin key provided
    if is_admin_key(x_admin_key):
        project = service.approve_project(db, project.id)
        logger.info(f"Auto-approved project id={project.id} via admin key")
    else:
        logger.info(f"Created project id={project.id} name='{project.projectName}'")
    return project


# ── PUT /api/templates/:id ────────────────────────────────────────────────────
@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project by ID",
    description="Partial update. Returns 409 if new name conflicts with another project.",
)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    project = service.update_project(db, project_id, data)
    logger.info(f"Updated project id={project_id}")
    return project


# ── PUT /api/templates/:id/approve ───────────────────────────────────────────
@router.put("/{project_id}/approve", response_model=ProjectResponse, summary="Approve project")
def approve_project(
    project_id: int,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    project = service.approve_project(db, project_id)
    logger.info(f"Approved project id={project_id}")
    return project


# ── PUT /api/templates/:id/reject ────────────────────────────────────────────
@router.put("/{project_id}/reject", response_model=ProjectResponse, summary="Reject project")
def reject_project(
    project_id: int,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    project = service.reject_project(db, project_id)
    logger.info(f"Rejected project id={project_id}")
    return project


# ── DELETE /api/templates/:id ────────────────────────────────────────────────
@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft delete")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    service.delete_project(db, project_id)
    logger.info(f"Soft-deleted project id={project_id}")
