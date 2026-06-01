"""
Server-Sent Events (SSE) endpoints for real-time chat.
Robust implementation that handles errors gracefully and ensures CORS works.
"""
import asyncio
import json
import logging
import time
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Query, Header, Request
from fastapi.responses import StreamingResponse

from app.auth.admin import is_admin_key
from app.realtime.event_bus import event_bus, Subscriber

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat/stream", tags=["Chat Realtime"])

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 15


def _format_sse(event_type: str, data: dict) -> str:
    """Format data as SSE event string."""
    json_data = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"


async def _sse_generator(
    request: Request,
    channel: str,
    subscriber: Subscriber,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE events. Handles disconnects and heartbeats."""
    try:
        logger.info(f"[TRACE] SSE CONNECTED → channel='{channel}' sub={subscriber.subscriber_id}")
        yield _format_sse("connected", {"channel": channel, "time": time.time()})

        last_heartbeat = time.time()

        while True:
            if await request.is_disconnected():
                logger.info(f"[TRACE] SSE DISCONNECTED → channel='{channel}'")
                break

            try:
                event = await asyncio.wait_for(
                    subscriber.queue.get(),
                    timeout=HEARTBEAT_INTERVAL
                )
                subscriber.touch()
                logger.info(f"[TRACE] SSE SENDING → channel='{channel}' event='{event['type']}'")
                yield _format_sse(event["type"], event["data"])
            except asyncio.TimeoutError:
                now = time.time()
                if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                    yield _format_sse("heartbeat", {"time": now})
                    last_heartbeat = now
                    subscriber.touch()
            except Exception as e:
                logger.error(f"[TRACE] SSE event error: {e}")
                break

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[TRACE] SSE generator error on '{channel}': {e}")
    finally:
        await event_bus.unsubscribe(channel, subscriber)


# ── GET /api/chat/stream/user?email= ─────────────────────────────────────────
@router.get("/user")
async def stream_user_chat(
    request: Request,
    email: str = Query(..., description="User email"),
):
    """User subscribes to their own chat thread via SSE."""
    try:
        email = email.strip().lower()
        channel = f"chat:{email}"
        subscriber = await event_bus.subscribe(channel)

        return StreamingResponse(
            _sse_generator(request, channel, subscriber),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logger.error(f"[TRACE] SSE /user endpoint error: {e}", exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"message": f"SSE connection failed: {str(e)}"},
            headers={"Access-Control-Allow-Origin": "*"},
        )


# ── GET /api/chat/stream/admin ────────────────────────────────────────────────
@router.get("/admin")
async def stream_admin_chat(
    request: Request,
    key: Optional[str] = Query(default=None, description="Admin key"),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Admin subscribes to all chat events via SSE."""
    try:
        channel = "admin:chat"
        subscriber = await event_bus.subscribe(channel)

        return StreamingResponse(
            _sse_generator(request, channel, subscriber),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logger.error(f"[TRACE] SSE /admin endpoint error: {e}", exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"message": f"SSE connection failed: {str(e)}"},
            headers={"Access-Control-Allow-Origin": "*"},
        )


# ── POST /api/chat/stream/typing ─────────────────────────────────────────────
@router.post("/typing", status_code=204)
async def send_typing(
    email: str = Query(..., description="Email of the person typing"),
    sender: str = Query(..., description="'user' or 'admin'"),
):
    """Broadcast typing indicator."""
    email = email.strip().lower()
    if sender == "user":
        await event_bus.publish("admin:chat", "typing", {"email": email, "sender": "user", "time": time.time()})
    elif sender == "admin":
        await event_bus.publish(f"chat:{email}", "typing", {"email": email, "sender": "admin", "time": time.time()})
    return None


# ── GET /api/chat/stream/status ───────────────────────────────────────────────
@router.get("/status")
async def get_stream_status():
    """Returns SSE connection statistics."""
    return {"status": "ok", "event_bus": event_bus.get_stats(), "heartbeat_interval": HEARTBEAT_INTERVAL}
