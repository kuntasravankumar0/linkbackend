"""
In-memory event bus for real-time chat notifications.
Uses asyncio queues to push events to SSE subscribers.
Production-grade: handles disconnects, memory limits, and multi-subscriber.
"""
import asyncio
import logging
import time
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Maximum events queued per subscriber before dropping oldest
MAX_QUEUE_SIZE = 100
# How long a subscriber can be idle before cleanup (seconds)
SUBSCRIBER_TIMEOUT = 300


@dataclass
class Subscriber:
    """A single SSE subscriber (one browser tab)."""
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=MAX_QUEUE_SIZE))
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    subscriber_id: str = ""

    def touch(self):
        self.last_active = time.time()

    def __hash__(self):
        return hash(self.subscriber_id)

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return self.subscriber_id == other.subscriber_id
        return False


class EventBus:
    """
    Pub/Sub event bus for real-time chat.
    
    Channels:
      - "chat:{email}" — user's chat thread updates
      - "admin:chat"   — admin gets notified of all new messages
      - "typing:{email}" — typing indicators
    """

    def __init__(self):
        self._channels: Dict[str, Set[Subscriber]] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._subscriber_count = 0

    def _get_lock(self) -> asyncio.Lock:
        """Lazy lock creation — ensures it's created in the correct event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def subscribe(self, channel: str) -> Subscriber:
        """Subscribe to a channel. Returns a Subscriber with a queue to read from."""
        lock = self._get_lock()
        async with lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._subscriber_count += 1
            sub = Subscriber(subscriber_id=f"sub_{self._subscriber_count}")
            self._channels[channel].add(sub)
            logger.info(f"[TRACE] EventBus: subscribed {sub.subscriber_id} to '{channel}' (total: {len(self._channels[channel])})")
            return sub

    async def unsubscribe(self, channel: str, subscriber: Subscriber):
        """Remove a subscriber from a channel."""
        lock = self._get_lock()
        async with lock:
            if channel in self._channels:
                self._channels[channel].discard(subscriber)
                if not self._channels[channel]:
                    del self._channels[channel]
                logger.debug(f"Unsubscribed {subscriber.subscriber_id} from '{channel}'")

    async def publish(self, channel: str, event_type: str, data: dict):
        """Publish an event to all subscribers on a channel."""
        lock = self._get_lock()
        async with lock:
            subscribers = self._channels.get(channel, set()).copy()

        if not subscribers:
            logger.info(f"[TRACE] publish → channel='{channel}' event='{event_type}' — NO SUBSCRIBERS (0 listeners)")
            return

        logger.info(f"[TRACE] publish → channel='{channel}' event='{event_type}' → {len(subscribers)} subscriber(s)")

        dropped = 0
        delivered = 0
        for sub in subscribers:
            try:
                # Non-blocking put — drop oldest if full
                if sub.queue.full():
                    try:
                        sub.queue.get_nowait()
                        dropped += 1
                    except asyncio.QueueEmpty:
                        pass
                sub.queue.put_nowait({"type": event_type, "data": data})
                sub.touch()
                delivered += 1
            except Exception as e:
                logger.warning(f"Failed to publish to {sub.subscriber_id}: {e}")

        logger.info(f"[TRACE] publish DONE → channel='{channel}' delivered={delivered} dropped={dropped}")

        if dropped:
            logger.warning(f"Dropped {dropped} old events on channel '{channel}' (queue full)")

    async def publish_multi(self, channels: list, event_type: str, data: dict):
        """Publish same event to multiple channels."""
        for channel in channels:
            await self.publish(channel, event_type, data)

    async def cleanup_stale(self):
        """Remove subscribers that haven't been active for SUBSCRIBER_TIMEOUT seconds."""
        now = time.time()
        lock = self._get_lock()
        async with lock:
            for channel in list(self._channels.keys()):
                stale = {s for s in self._channels[channel]
                        if now - s.last_active > SUBSCRIBER_TIMEOUT}
                for s in stale:
                    self._channels[channel].discard(s)
                    logger.debug(f"Cleaned up stale subscriber {s.subscriber_id}")
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_stats(self) -> dict:
        """Get event bus statistics."""
        total_subs = sum(len(subs) for subs in self._channels.values())
        return {
            "channels": len(self._channels),
            "total_subscribers": total_subs,
            "channel_details": {
                ch: len(subs) for ch, subs in self._channels.items()
            }
        }


# Global singleton
event_bus = EventBus()
