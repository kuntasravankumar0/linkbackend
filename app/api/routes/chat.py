"""
Chat routes.
Base prefix: /api/chat

Route naming avoids FastAPI path-param conflicts:
  /api/chat/send              POST  — user sends a message (public)
  /api/chat/history           GET   — user fetches own thread by ?email= (public)
  /api/chat/admin/threads     GET   — admin: all thread summaries
  /api/chat/admin/thread      GET   — admin: full thread by ?email= + mark read
  /api/chat/admin/reply       POST  — admin sends a reply
  /api/chat/admin/thread/del  DELETE — admin deletes thread by ?email=
  /api/chat/stream/*          GET   — SSE realtime streams (see realtime/sse.py)
"""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, status, Header, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.auth.admin import require_admin
from app.db.database import get_db
from app.schemas.chat import (
    ChatMessageCreate, AdminReplyCreate,
    ChatMessageResponse, ChatThreadResponse, ChatListResponse,
)
import app.services.chat_service as service
from app.realtime.event_bus import event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


def _publish_event_sync(channels, event_type, data):
    """Helper to publish events from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(event_bus.publish_multi(channels, event_type, data))
        else:
            loop.run_until_complete(event_bus.publish_multi(channels, event_type, data))
    except RuntimeError:
        # No event loop — create one
        loop = asyncio.new_event_loop()
        loop.run_until_complete(event_bus.publish_multi(channels, event_type, data))


# ── POST /api/chat/send ───────────────────────────────────────────────────────
@router.post(
    "/send",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User sends a chat message (public)",
)
async def send_message(
    data: ChatMessageCreate,
    db: Session = Depends(get_db),
):
    logger.info(f"[TRACE] USER SEND → email={data.email} message='{data.message[:50]}...'")
    result = service.send_user_message(db, data)
    logger.info(f"[TRACE] USER SEND → DB SAVED id={result.id} email={result.email}")
    # Push realtime notification
    msg_data = {
        "id": result.id,
        "email": result.email,
        "name": result.name,
        "sender": result.sender,
        "message": result.message,
        "is_read": result.is_read,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }
    try:
        logger.info(f"[TRACE] USER SEND → EMITTING SSE to channels: chat:{result.email}, admin:chat")
        await event_bus.publish_multi(
            [f"chat:{result.email}", "admin:chat"],
            "new_message",
            {"email": result.email, "message": msg_data, "sender": "user"}
        )
        logger.info(f"[TRACE] USER SEND → SSE EMITTED SUCCESSFULLY")
    except Exception as e:
        logger.error(f"[TRACE] USER SEND → SSE EMIT FAILED: {e}")
    return result


# ── GET /api/chat/history?email= ──────────────────────────────────────────────
@router.get(
    "/history",
    response_model=ChatThreadResponse,
    summary="Get chat thread by email — user's own view (public)",
)
def get_user_thread(
    email: str = Query(..., description="User's email address"),
    db: Session = Depends(get_db),
):
    return service.get_thread_for_user(db, email)


# ── GET /api/chat/admin/threads ───────────────────────────────────────────────
@router.get(
    "/admin/threads",
    response_model=ChatListResponse,
    summary="[Admin] List all chat threads",
)
def list_threads(
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    return service.get_all_threads(db)


# ── GET /api/chat/admin/thread?email= ────────────────────────────────────────
@router.get(
    "/admin/thread",
    response_model=ChatThreadResponse,
    summary="[Admin] Get full thread + mark read",
)
async def get_thread_admin(
    email: str = Query(..., description="User's email address"),
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    result = service.get_thread_admin(db, email)
    # Notify user that their messages were read
    try:
        await event_bus.publish(f"chat:{email.strip().lower()}", "messages_read", {
            "email": email.strip().lower(),
        })
    except Exception:
        pass
    return result


# ── POST /api/chat/admin/reply ────────────────────────────────────────────────
@router.post(
    "/admin/reply",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Reply to a user's chat thread",
)
async def admin_reply(
    data: AdminReplyCreate,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    logger.info(f"[TRACE] ADMIN REPLY → email={data.email} message='{data.message[:50]}...'")
    result = service.admin_reply(db, data)
    logger.info(f"[TRACE] ADMIN REPLY → DB SAVED id={result.id} email={result.email}")
    # Push realtime notification
    msg_data = {
        "id": result.id,
        "email": result.email,
        "name": result.name,
        "sender": result.sender,
        "message": result.message,
        "is_read": result.is_read,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }
    try:
        logger.info(f"[TRACE] ADMIN REPLY → EMITTING SSE to channels: chat:{result.email}, admin:chat")
        await event_bus.publish_multi(
            [f"chat:{result.email}", "admin:chat"],
            "new_message",
            {"email": result.email, "message": msg_data, "sender": "admin"}
        )
        logger.info(f"[TRACE] ADMIN REPLY → SSE EMITTED SUCCESSFULLY")
    except Exception as e:
        logger.error(f"[TRACE] ADMIN REPLY → SSE EMIT FAILED: {e}")
    return result


# ── DELETE /api/chat/admin/thread?email= ─────────────────────────────────────
@router.delete(
    "/admin/thread",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Delete entire chat thread",
)
async def delete_thread(
    email: str = Query(..., description="User's email address"),
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    require_admin(x_admin_key)
    service.delete_thread(db, email)
    # Notify about thread deletion
    try:
        await event_bus.publish_multi(
            [f"chat:{email.strip().lower()}", "admin:chat"],
            "thread_deleted",
            {"email": email.strip().lower()}
        )
    except Exception:
        pass
