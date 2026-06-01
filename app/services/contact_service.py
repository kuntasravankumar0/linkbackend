"""
Service layer for ContactMessage — business logic.
"""
import logging
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.contact import ContactMessage
from app.schemas.contact import ContactCreate, ContactResponse, ContactListResponse
import app.repositories.contact_repository as repo

logger = logging.getLogger(__name__)


def _to_response(msg: ContactMessage) -> ContactResponse:
    return ContactResponse(
        id=msg.id,
        name=msg.name,
        email=msg.email,
        phone=msg.phone,
        subject=msg.subject,
        message=msg.message,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


def _not_found(msg_id):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": f"Contact message '{msg_id}' not found.", "errors": None},
    )


def get_all(db: Session) -> ContactListResponse:
    messages = repo.get_all(db)
    unread   = repo.get_unread_count(db)
    return ContactListResponse(
        content=[_to_response(m) for m in messages],
        total=len(messages),
        unread=unread,
    )


def create_message(db: Session, data: ContactCreate) -> ContactResponse:
    try:
        logger.debug(f"Creating contact message from {data.email}")
        msg = repo.create(db, data)
        logger.info(f"New contact message id={msg.id} from={msg.email}")
        return _to_response(msg)
    except Exception as e:
        logger.error(
            f"Service error creating contact message: {type(e).__name__}: {str(e)[:200]}",
            exc_info=True
        )
        raise


def mark_read(db: Session, msg_id: int) -> ContactResponse:
    msg = repo.get_by_id(db, msg_id)
    if not msg:
        _not_found(msg_id)
    updated = repo.mark_read(db, msg)
    return _to_response(updated)


def mark_unread(db: Session, msg_id: int) -> ContactResponse:
    msg = repo.get_by_id(db, msg_id)
    if not msg:
        _not_found(msg_id)
    updated = repo.mark_unread(db, msg)
    return _to_response(updated)


def delete_message(db: Session, msg_id: int) -> None:
    msg = repo.get_by_id(db, msg_id)
    if not msg:
        _not_found(msg_id)
    repo.soft_delete(db, msg)
    logger.info(f"Deleted contact message id={msg_id}")
