"""
Service layer for Chat — business logic.
Optimized: eliminated N+1 queries, added efficient batch operations.
"""
import logging
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.chat import ChatMessage
from app.schemas.chat import (
    ChatMessageCreate, AdminReplyCreate,
    ChatMessageResponse, ChatThreadSummary,
    ChatThreadResponse, ChatListResponse,
)
import app.repositories.chat_repository as repo

logger = logging.getLogger(__name__)


def _to_response(msg: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg.id,
        email=msg.email,
        name=msg.name,
        sender=msg.sender,
        message=msg.message,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


# ── Public ─────────────────────────────────────────────────────────────────────

def send_user_message(db: Session, data: ChatMessageCreate) -> ChatMessageResponse:
    msg = repo.create_user_message(db, data)
    logger.info(f"User chat from={msg.email}")
    return _to_response(msg)


def get_thread_for_user(db: Session, email: str) -> ChatThreadResponse:
    """Return all messages for a given email (user's own view)."""
    email = email.strip().lower()
    messages = repo.get_thread(db, email)
    name = repo.get_name_for_email(db, email)
    return ChatThreadResponse(
        email=email,
        name=name,
        messages=[_to_response(m) for m in messages],
    )


# ── Admin ──────────────────────────────────────────────────────────────────────

def get_all_threads(db: Session) -> ChatListResponse:
    """Admin: list all threads with summary info — optimized single-pass."""
    # Use optimized batch query instead of N+1
    thread_summaries = repo.get_all_thread_summaries(db)
    threads: List[ChatThreadSummary] = []
    
    for summary in thread_summaries:
        threads.append(ChatThreadSummary(
            email=summary["email"],
            name=summary["name"],
            last_message=summary["last_message"][:120],
            last_at=summary["last_at"],
            unread=summary["unread"],
            total=summary["total"],
        ))
    
    # Sort by latest message descending
    threads.sort(key=lambda t: t.last_at, reverse=True)
    total_unread = sum(t.unread for t in threads)
    return ChatListResponse(threads=threads, total_unread=total_unread)


def get_thread_admin(db: Session, email: str) -> ChatThreadResponse:
    """Admin: get full thread and mark all user messages as read."""
    email = email.strip().lower()
    repo.mark_thread_read(db, email)
    messages = repo.get_thread(db, email)
    name = repo.get_name_for_email(db, email)
    return ChatThreadResponse(
        email=email,
        name=name,
        messages=[_to_response(m) for m in messages],
    )


def admin_reply(db: Session, data: AdminReplyCreate) -> ChatMessageResponse:
    msg = repo.create_admin_reply(db, data)
    logger.info(f"Admin replied to={msg.email}")
    return _to_response(msg)


def delete_thread(db: Session, email: str) -> None:
    email = email.strip().lower()
    count = repo.soft_delete_thread(db, email)
    logger.info(f"Deleted chat thread email={email} ({count} messages)")
