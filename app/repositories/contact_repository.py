"""
Repository layer for ContactMessage — raw DB queries only.
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.contact import ContactMessage
from app.schemas.contact import ContactCreate

logger = logging.getLogger(__name__)


def _active(db: Session):
    return db.query(ContactMessage).filter(ContactMessage.is_deleted == False)  # noqa: E712


def get_all(db: Session) -> List[ContactMessage]:
    return _active(db).order_by(ContactMessage.created_at.desc()).all()


def get_by_id(db: Session, msg_id: int) -> Optional[ContactMessage]:
    return _active(db).filter(ContactMessage.id == msg_id).first()


def get_unread_count(db: Session) -> int:
    return _active(db).filter(ContactMessage.is_read == False).count()  # noqa: E712


def create(db: Session, data: ContactCreate) -> ContactMessage:
    try:
        msg = ContactMessage(
            name=data.name,
            email=data.email,
            phone=data.phone,
            subject=data.subject,
            message=data.message,
            is_read=False,
            is_deleted=False,
        )
        db.add(msg)
        logger.debug(f"Contact message prepared: name={data.name}, email={data.email}")
        
        db.commit()
        logger.info(f"Contact message committed: id={msg.id}, email={msg.email}")
        
        db.refresh(msg)
        logger.debug(f"Created contact message id={msg.id} from={msg.email}")
        return msg
    except Exception as e:
        logger.error(
            f"Failed to create contact message from {data.email}: {type(e).__name__}: {str(e)[:200]}",
            exc_info=True
        )
        raise


def mark_read(db: Session, msg: ContactMessage) -> ContactMessage:
    msg.is_read = True
    db.commit()
    db.refresh(msg)
    return msg


def mark_unread(db: Session, msg: ContactMessage) -> ContactMessage:
    msg.is_read = False
    db.commit()
    db.refresh(msg)
    return msg


def soft_delete(db: Session, msg: ContactMessage) -> None:
    msg.is_deleted = True
    db.commit()
    logger.debug(f"Soft-deleted contact message id={msg.id}")
