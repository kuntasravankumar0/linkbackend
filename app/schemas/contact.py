"""
Pydantic v2 schemas for Contact Messages.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ── Request ────────────────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name:    str           = Field(..., min_length=1, max_length=255)
    email:   str           = Field(..., min_length=3, max_length=255)
    phone:   Optional[str] = Field(None, max_length=30)
    subject: Optional[str] = Field(None, max_length=255)
    message: str           = Field(..., min_length=1)

    @field_validator("name", "message")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be blank.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address.")
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def empty_phone_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


# ── Response ───────────────────────────────────────────────────────────────────

class ContactResponse(BaseModel):
    id:         int
    name:       str
    email:      str
    phone:      Optional[str] = None
    subject:    Optional[str] = None
    message:    str
    is_read:    bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactListResponse(BaseModel):
    content: List[ContactResponse]
    total:   int
    unread:  int
