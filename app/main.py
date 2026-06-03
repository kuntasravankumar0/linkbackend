"""
FastAPI application — production-ready entry point.
Port: 8081 (matches frontend VITE_API_BASE_URL default)
"""
import logging
import os
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config.settings import settings
from app.db.database import engine
from app.db.schema import ensure_database_schema
from app.api.routes import templates, contact, chat
from app.realtime.sse import router as sse_router
from app.middleware.error_handler import (
    validation_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler,
)
from app.middleware.rate_limiter import RateLimiterMiddleware

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Ensure Database Schema is Up to Date ──────────────────────────────────────────
try:
    import os
    from alembic.config import Config
    from alembic import command
    
    # Import all models so Base.metadata knows about them
    from app.models import Project, ContactMessage, ChatMessage
    ensure_database_schema(engine)
    
    # If using SQLite fallback, just create tables directly (Alembic migrations are MySQL-specific)
    if "sqlite" in str(engine.url):
        logger.info("SQLite fallback detected — creating tables directly...")
        logger.info("SQLite tables created successfully.")
    elif os.getenv("VERCEL"):
        logger.info("Skipping Alembic on Vercel; schema guard already ran.")
    else:
        logger.info("Verifying database schema with Alembic...")
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini_path = os.path.join(os.path.dirname(backend_dir), "alembic.ini")
        
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(backend_dir), "alembic"))
        
        try:
            command.upgrade(alembic_cfg, "head")
            logger.info("Database schema is up to date.")
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "duplicate" in err_str:
                logger.info("Tables already exist. Stamping DB to head...")
                command.stamp(alembic_cfg, "head")
            elif "no such table" in err_str or "doesn't exist" in err_str:
                logger.warning(f"Migration skipped (table may not exist yet): {e}")
            else:
                raise e
except Exception as e:
    logger.warning(f"Schema verification skipped: {type(e).__name__}: {str(e)[:100]}")
    # Continue — if it fails in a restrictive env, hope the schema is already correct

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ForYou — Project Gallery API",
    description=(
        "Production-ready backend for the ForYou project/template gallery platform.\n\n"
        "All endpoints match the frontend's axios service exactly."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "ForYou Platform"},
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# Use origins from .env + always include common local dev ports
_cors_origins = settings.cors_origins_list
# Ensure local dev origins are always included
for origin in ["http://localhost:3000", "https://linkfrontend.onrender.com", "http://localhost:8081"]:
    if origin not in _cors_origins:
        _cors_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow ALL origins — SSE EventSource needs this
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── GZip Compression — reduces response size by 60-80% ────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=500)

# ── Rate Limiting — prevent API abuse ─────────────────────────────────────────
app.add_middleware(RateLimiterMiddleware)

# ── Security headers — added via ASGI middleware (does NOT buffer SSE) ─────────
class SecurityHeadersMiddleware:
    """Pure ASGI middleware that adds security headers without buffering responses."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # Skip SSE streams entirely — no wrapping, no buffering
        if path.startswith("/api/chat/stream"):
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                extra_headers = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                ]
                message["headers"] = list(message.get("headers", [])) + extra_headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

app.add_middleware(SecurityHeadersMiddleware)

# ── Exception handlers ─────────────────────────────────────────────────────────
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Startup/Shutdown Events ────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Log startup info and start background tasks."""
    import asyncio
    from app.realtime.event_bus import event_bus
    
    logger.info(f"Starting ForYou API v2.0.0")
    logger.info(f"Environment: {'DEBUG' if settings.DEBUG else 'PRODUCTION'}")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT} (SSL: {bool(settings.DB_SSL_CA)})")
    logger.info(f"SQLAlchemy engine driver: {engine.url.drivername}")
    logger.info(f"Connection Pool: NullPool (serverless-optimized)")
    logger.info(f"Realtime: SSE event bus active")
    
    # Start periodic cleanup of stale SSE subscribers
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(60)
            await event_bus.cleanup_stale()
    
    asyncio.create_task(_cleanup_loop())


@app.on_event("shutdown")
def shutdown_event():
    """Log shutdown info."""
    logger.info("Shutting down ForYou API")

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(templates.router, prefix="/api")
app.include_router(contact.router,   prefix="/api")
app.include_router(chat.router,      prefix="/api")
app.include_router(sse_router,       prefix="/api")

# ── Health & Info ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    """Quick health check — used by load balancers and monitoring."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "commit": os.getenv("VERCEL_GIT_COMMIT_SHA", "local")[:12],
        "port": settings.APP_PORT,
        "debug": settings.DEBUG,
        "database": engine.url.drivername,
    }

def get_database_hint() -> str:
    """Provide a human-friendly hint when the database is the only failing subsystem."""
    if "mysql" in engine.url.drivername:
        return (
            "If the only issue is MySQL/database connectivity, verify DB credentials, SSL CA path, "
            "and network access. The API services are otherwise configured to run."
        )

    if "sqlite" in engine.url.drivername:
        return (
            "SQLite fallback is active. For production, disable DB_FALLBACK_SQLITE and use cloud MySQL."
        )

    return "For database diagnostics, use /health/db."


@app.get("/health/db", tags=["System"])
def database_health():
    """Safe production DB diagnostic: no credentials, only schema/query status."""
    import os as os_module
    
    # Check SSL certificate if configured
    ssl_diagnostic = {}
    if settings.DB_SSL_CA:
        backend_root = os_module.path.dirname(os_module.path.dirname(os_module.path.dirname(__file__)))
        ca_path = os_module.path.join(backend_root, settings.DB_SSL_CA)
        ssl_diagnostic["configured"] = True
        ssl_diagnostic["path"] = ca_path
        ssl_diagnostic["exists"] = os_module.path.exists(ca_path)
        
        if not os_module.path.exists(ca_path):
            # Try Vercel path
            alt_path = f"/vercel/path0/{settings.DB_SSL_CA}"
            ssl_diagnostic["alt_path"] = alt_path
            ssl_diagnostic["alt_exists"] = os_module.path.exists(alt_path)
    
    try:
        inspector = inspect(engine)
        tables = sorted(inspector.get_table_names())
        result = {"status": "ok", "database": engine.url.drivername, "tables": tables}
        
        if ssl_diagnostic:
            result["ssl_certificate"] = ssl_diagnostic

        if inspector.has_table("alldata"):
            result["alldata_columns"] = [
                column["name"] for column in inspector.get_columns("alldata")
            ]
            with engine.connect() as conn:
                result["alldata_count"] = conn.execute(
                    text("SELECT COUNT(*) FROM alldata")
                ).scalar()
                result["templates_query"] = conn.execute(
                    text(
                        "SELECT id, unique_id, project_name, access_type, approval_status "
                        "FROM alldata WHERE is_deleted = 0 ORDER BY created_at DESC LIMIT 1"
                    )
                ).mappings().first() is not None

        result["message"] = (
            "Database check passed. If the rest of the API is reachable and this fails, "
            "your MySQL/database connection is likely the only problem."
        )
        result["hint"] = get_database_hint()
        return result
    except Exception as exc:
        error_response = {
            "status": "error",
            "database": engine.url.drivername,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
            "message": (
                "If this is the only issue, your database/MySQL connection is likely failing while "
                "the rest of the API remains available."
            ),
            "hint": get_database_hint(),
        }
        if ssl_diagnostic:
            error_response["ssl_certificate"] = ssl_diagnostic
        
        return JSONResponse(
            status_code=500,
            content=error_response,
        )


@app.get("/health/ssl", tags=["System"])
def ssl_health():
    """Diagnostic endpoint: Check SSL certificate availability WITHOUT database access."""
    import os as os_module
    
    result = {
        "ssl_configured": bool(settings.DB_SSL_CA),
        "database_host": f"{settings.DB_HOST}:{settings.DB_PORT}",
        "aiven_required_ssl": True,
    }
    
    if not settings.DB_SSL_CA:
        result["message"] = "No SSL certificate configured"
        return JSONResponse(status_code=400, content=result)
    
    # Check all possible certificate paths
    backend_root = os_module.path.dirname(os_module.path.dirname(os_module.path.dirname(__file__)))
    paths_to_check = [
        ("computed", os_module.path.join(backend_root, settings.DB_SSL_CA)),
        ("vercel", "/vercel/path0/ssl/ca.pem"),
        ("absolute", f"/{settings.DB_SSL_CA.lstrip('/')}" ),
    ]
    
    result["paths_checked"] = {}
    found_cert = None
    
    for name, path in paths_to_check:
        exists = os_module.path.exists(path)
        result["paths_checked"][name] = {
            "path": path,
            "exists": exists,
        }
        
        if exists and not found_cert:
            try:
                with open(path, 'r') as f:
                    content = f.read()
                    is_valid = "BEGIN CERTIFICATE" in content
                    result["paths_checked"][name]["valid"] = is_valid
                    if is_valid:
                        found_cert = {
                            "path": path,
                            "size_bytes": len(content),
                            "lines": content.count('\n'),
                        }
            except Exception as e:
                result["paths_checked"][name]["error"] = str(e)
    
    if found_cert:
        result["status"] = "ok"
        result["certificate"] = found_cert
        result["message"] = f"SSL certificate found and valid at: {found_cert['path']}"
    else:
        result["status"] = "error"
        result["message"] = "SSL certificate NOT found at any location. Database connection will fail."
    
    return result


@app.get("/", tags=["System"])
def root():
    return {
        "message": "ForYou API is running",
        "docs": "/docs",
        "health": "/health",
        "ssl_diagnostic": "/health/ssl",
        "database_health": "/health/db",
        "database_hint": get_database_hint(),
        "api": "/api/templates",
    }
