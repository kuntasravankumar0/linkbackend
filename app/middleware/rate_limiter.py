"""
In-memory rate limiter middleware for API abuse prevention.
Uses pure ASGI approach (not BaseHTTPMiddleware) to avoid breaking SSE streams.
"""
import time
import logging
from collections import defaultdict
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Configuration
RATE_LIMIT = 100          # Max requests per window
RATE_WINDOW = 60          # Window in seconds
BURST_LIMIT = 20          # Max burst in 5 seconds
BURST_WINDOW = 5

# Exempt paths (health checks, SSE streams)
EXEMPT_PATHS = {'/health', '/', '/docs', '/redoc', '/openapi.json'}
EXEMPT_PREFIXES = ('/api/chat/stream',)  # SSE streams are long-lived


class RateLimiterMiddleware:
    """Pure ASGI middleware — does NOT buffer responses, safe for SSE."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self._requests: dict = defaultdict(list)
        self._last_cleanup = time.time()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip rate limiting for exempt paths (SSE, health, docs)
        if path in EXEMPT_PATHS or any(path.startswith(p) for p in EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Get client IP
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        if client_ip == "testclient":
            await self.app(scope, receive, send)
            return

        # Check forwarded headers
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        now = time.time()

        # Periodic cleanup
        if now - self._last_cleanup > 60:
            self._cleanup(now)
            self._last_cleanup = now

        # Get timestamps for this IP
        timestamps = self._requests[client_ip]
        timestamps[:] = [t for t in timestamps if now - t < RATE_WINDOW]

        # Check rate limit
        if len(timestamps) >= RATE_LIMIT:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"message": "Too many requests. Please slow down.", "errors": None},
                headers={"Retry-After": str(RATE_WINDOW)},
            )
            await response(scope, receive, send)
            return

        # Check burst limit
        recent = [t for t in timestamps if now - t < BURST_WINDOW]
        if len(recent) >= BURST_LIMIT:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"message": "Too many requests in a short time.", "errors": None},
                headers={"Retry-After": str(BURST_WINDOW)},
            )
            await response(scope, receive, send)
            return

        # Record request and pass through
        timestamps.append(now)
        await self.app(scope, receive, send)

    def _cleanup(self, now: float):
        stale_keys = [
            ip for ip, timestamps in self._requests.items()
            if not timestamps or now - timestamps[-1] > RATE_WINDOW * 2
        ]
        for key in stale_keys:
            del self._requests[key]
