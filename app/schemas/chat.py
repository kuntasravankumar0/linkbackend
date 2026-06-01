"""
Pydantic v2 schemas for Chat Messages.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class ChatMessageCreate(BaseModel):
    """User sends a message — public endpoint."""
    email:   str = Field(..., min_length=3, max_length=255)
    name:    Optional[str] = Field(None, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address.")
        if len(v) > 255:
            raise ValueError("Email too long.")
        # Basic XSS prevention
        if "<" in v or ">" in v or "javascript:" in v.lower():
            raise ValueError("Invalid characters in email.")
        return v

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be blank.")
        if len(v) > 5000:
            raise ValueError("Message too long (max 5000 characters).")
        return v

    @field_validator("name", mode="before")
    @classmethod
    def empty_name_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        if isinstance(v, str) and len(v) > 255:
            return v[:255]
        return v


class AdminReplyCreate(BaseModel):
    """Admin sends a reply — admin-only endpoint."""
    email:   str = Field(..., min_length=3, max_length=255)
    message: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be blank.")
        return v


class ChatMessageResponse(BaseModel):
    id:         int
    email:      str
    name:       Optional[str] = None
    sender:     str
    message:    str
    is_read:    bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatThreadSummary(BaseModel):
    """One row per unique email — shown in admin thread list."""
    email:        str
    name:         Optional[str] = None
    last_message: str
    last_at:      datetime
    unread:       int
    total:        int


class ChatThreadResponse(BaseModel):
    """Full thread for one email."""
    email:    str
    name:     Optional[str] = None
    messages: List[ChatMessageResponse]


class ChatListResponse(BaseModel):
    """Admin: all threads summary."""
    threads:      List[ChatThreadSummary]
    total_unread: int
