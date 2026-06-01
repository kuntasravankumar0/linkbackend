"""Shared admin-key helpers for protected admin endpoints."""
import hashlib
from typing import Optional

from fastapi import HTTPException, status

from app.config.settings import settings


def is_admin_key(key: Optional[str]) -> bool:
    if not key:
        return False
    return hashlib.sha256(key.strip().encode()).hexdigest() == settings.ADMIN_KEY_HASH


def require_admin(key: Optional[str]) -> None:
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Admin key required.", "errors": None},
        )
    if not is_admin_key(key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Invalid admin key.", "errors": None},
        )
