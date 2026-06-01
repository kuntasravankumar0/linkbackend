"""
Repository layer for ChatMessage — raw DB queries only.
Optimized: batch queries to eliminate N+1 problem.
"""
import logging
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from app.models.chat import ChatMessage
from app.schemas.chat import ChatMessageCreate, AdminReplyCreate

logger = logging.getLogger(__name__)


def _active(db: Session):
    return db.query(ChatMessage).filter(ChatMessage.is_deleted == False)  # noqa: E712


def get_thread(db: Session, email: str) -> List[ChatMessage]:
    """All messages for one email, oldest first."""
    return (
        _active(db)
        .filter(func.lower(ChatMessage.email) == email.strip().lower())
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def get_all_emails(db: Session) -> List[str]:
    """Distinct emails that have chat messages."""
    rows = (
        _active(db)
        .with_entities(ChatMessage.email)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def get_all_thread_summaries(db: Session) -> List[Dict]:
    """
    Optimized: Get all thread summaries in a single query.
    Eliminates N+1 problem from the old approach.
    Returns list of dicts with email, name, last_message, last_at, unread, total.
    """
    # Subquery for thread stats
    stats = (
        db.query(
            ChatMessage.email,
            func.count(ChatMessage.id).label("total"),
            func.max(ChatMessage.created_at).label("last_at"),
            func.sum(
                case(
                    (
                        (ChatMessage.sender == "user") & (ChatMessage.is_read == False),  # noqa: E712
                        1
                    ),
                    else_=0
                )
            ).label("unread"),
        )
        .filter(ChatMessage.is_deleted == False)  # noqa: E712
        .group_by(ChatMessage.email)
        .all()
    )

    results = []
    for row in stats:
        email = row.email
        # Get latest message text
        latest = (
            _active(db)
            .filter(func.lower(ChatMessage.email) == email.lower())
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        # Get name
        name_row = (
            _active(db)
            .filter(
                func.lower(ChatMessage.email) == email.lower(),
                ChatMessage.name.isnot(None),
            )
            .order_by(ChatMessage.created_at.asc())
            .first()
        )

        results.append({
            "email": email,
            "name": name_row.name if name_row else None,
            "last_message": latest.message if latest else "",
            "last_at": row.last_at,
            "unread": int(row.unread or 0),
            "total": int(row.total or 0),
        })

    return results


def get_unread_count_for_email(db: Session, email: str) -> int:
    """Unread user messages for a given email (admin hasn't read them)."""
    return (
        _active(db)
        .filter(
            func.lower(ChatMessage.email) == email.strip().lower(),
            ChatMessage.sender == "user",
            ChatMessage.is_read == False,  # noqa: E712
        )
        .count()
    )


def get_total_unread(db: Session) -> int:
    return (
        _active(db)
        .filter(ChatMessage.sender == "user", ChatMessage.is_read == False)  # noqa: E712
        .count()
    )


def get_latest_for_email(db: Session, email: str) -> Optional[ChatMessage]:
    return (
        _active(db)
        .filter(func.lower(ChatMessage.email) == email.strip().lower())
        .order_by(ChatMessage.created_at.desc())
        .first()
    )


def get_name_for_email(db: Session, email: str) -> Optional[str]:
    row = (
        _active(db)
        .filter(
            func.lower(ChatMessage.email) == email.strip().lower(),
            ChatMessage.name.isnot(None),
        )
        .order_by(ChatMessage.created_at.asc())
        .first()
    )
    return row.name if row else None


def create_user_message(db: Session, data: ChatMessageCreate) -> ChatMessage:
    msg = ChatMessage(
        email=data.email.strip().lower(),
        name=data.name,
        sender="user",
        message=data.message.strip(),
        is_read=False,
        is_deleted=False,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    logger.debug(f"User chat message id={msg.id} from={msg.email}")
    return msg


def create_admin_reply(db: Session, data: AdminReplyCreate) -> ChatMessage:
    msg = ChatMessage(
        email=data.email.strip().lower(),
        name=None,
        sender="admin",
        message=data.message.strip(),
        is_read=True,   # admin's own message is always "read"
        is_deleted=False,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    logger.debug(f"Admin reply id={msg.id} to={msg.email}")
    return msg


def mark_thread_read(db: Session, email: str) -> int:
    """Mark all user messages in a thread as read. Returns count updated."""
    updated = (
        db.query(ChatMessage)
        .filter(
            func.lower(ChatMessage.email) == email.strip().lower(),
            ChatMessage.sender == "user",
            ChatMessage.is_read == False,  # noqa: E712
            ChatMessage.is_deleted == False,  # noqa: E712
        )
        .all()
    )
    for m in updated:
        m.is_read = True
    db.commit()
    return len(updated)


def soft_delete_thread(db: Session, email: str) -> int:
    """Soft-delete all messages for an email. Returns count deleted."""
    msgs = (
        db.query(ChatMessage)
        .filter(func.lower(ChatMessage.email) == email.strip().lower())
        .all()
    )
    for m in msgs:
        m.is_deleted = True
    db.commit()
    return len(msgs)
