"""
Contact message routes.
Base prefix: /api/contact

Public:
  POST /api/contact          — submit a contact message (no auth required)

Admin-only (requires X-Admin-Key header):
  GET  /api/contact          — list all messages
  PUT  /api/contact/:id/read   — mark as read
  PUT  /api/contact/:id/unread — mark as unread
  DELETE /api/contact/:id    — soft delete
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, status, Header
from sqlalchemy.orm import Session

from app.auth.admin import require_admin
from app.db.database import get_db
from app.schemas.contact import ContactCreate, ContactResponse, ContactListResponse
import app.services.contact_service as service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contact", tags=["Contact"])

# ── POST /api/contact ─────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a contact message",
)
def submit_contact(data: ContactCreate, db: Session = Depends(get_db)):
    return service.create_message(db, data)


# ── GET /api/contact ──────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=ContactListResponse,
    summary="[Admin] List all contact messages",
)
def list_messages(
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    return service.get_all(db)


# ── PUT /api/contact/:id/read ─────────────────────────────────────────────────
@router.put(
    "/{msg_id}/read",
    response_model=ContactResponse,
    summary="[Admin] Mark message as read",
)
def mark_read(
    msg_id: int,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    return service.mark_read(db, msg_id)


# ── PUT /api/contact/:id/unread ───────────────────────────────────────────────
@router.put(
    "/{msg_id}/unread",
    response_model=ContactResponse,
    summary="[Admin] Mark message as unread",
)
def mark_unread(
    msg_id: int,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    return service.mark_unread(db, msg_id)


# ── DELETE /api/contact/:id ───────────────────────────────────────────────────
@router.delete(
    "/{msg_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Delete contact message",
)
def delete_message(
    msg_id: int,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    service.delete_message(db, msg_id)
