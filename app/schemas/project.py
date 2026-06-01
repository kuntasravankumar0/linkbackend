"""
Pydantic v2 schemas.
All field names match the frontend exactly — camelCase in, camelCase out.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from enum import Enum


class AccessType(str, Enum):
    FREE = "FREE"
    PAID = "PAID"
    BOTH = "BOTH"


class ApprovalStatus(str, Enum):
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ── Request schemas ────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    """
    POST /api/templates
    Sent by AddProject.jsx — all fields match formData state keys exactly.
    """
    projectName:    str            = Field(..., min_length=1, max_length=255)
    subCategory:    Optional[str]  = Field(None, max_length=100)
    accessType:     AccessType     = AccessType.FREE
    details:        Optional[str]  = None
    subdetails:     Optional[str]  = None
    guide:          Optional[str]  = None
    source:         Optional[str]  = Field(None, max_length=255)
    link:           Optional[str]  = Field(None, max_length=500)
    image:          Optional[str]  = Field(None, max_length=500)
    implementation: Optional[str]  = None

    @field_validator("projectName")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be blank.")
        return v

    @field_validator("link", "image", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        """Convert empty strings to None for optional URL fields."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class ProjectUpdate(BaseModel):
    """
    PUT /api/templates/:id
    Sent by AdminProjects.jsx edit modal — all fields optional (partial update).
    """
    projectName:    Optional[str]        = Field(None, min_length=1, max_length=255)
    subCategory:    Optional[str]        = Field(None, max_length=100)
    accessType:     Optional[AccessType] = None
    details:        Optional[str]        = None
    subdetails:     Optional[str]        = None
    guide:          Optional[str]        = None
    source:         Optional[str]        = Field(None, max_length=255)
    link:           Optional[str]        = Field(None, max_length=500)
    image:          Optional[str]        = Field(None, max_length=500)
    implementation: Optional[str]        = None

    @field_validator("link", "image", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


# ── Response schemas ───────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    """
    Single project response.
    Field names match exactly what the frontend reads:
      project.id, project.uniqueId, project.projectName,
      project.subCategory, project.accessType, project.details,
      project.subdetails, project.guide, project.source,
      project.link, project.image, project.implementation,
      project.approvalStatus
    """
    id:             int
    uniqueId:       str
    projectName:    str
    subCategory:    Optional[str] = None
    accessType:     str
    details:        Optional[str] = None
    subdetails:     Optional[str] = None
    guide:          Optional[str] = None
    source:         Optional[str] = None
    link:           Optional[str] = None
    image:          Optional[str] = None
    implementation: Optional[str] = None
    approvalStatus: str

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """
    List wrapper.
    Frontend reads: response.data.content
    """
    content: List[ProjectResponse]


# ── Error schema ───────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """
    Standard error shape.
    Frontend reads:
      error.response?.data?.message
      error.response?.data?.errors?.fieldName
    """
    message: str
    errors:  Optional[dict] = None
