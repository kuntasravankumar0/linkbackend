"""
Database engine, session factory, and Base class.
SSL is configured automatically when DB_SSL_CA is set in .env (Aiven cloud).
Serverless-optimized: uses NullPool for Vercel/AWS Lambda (no connection pooling).
Connection retry logic for transient network failures.
"""
import os
import logging
import socket
import time
from sqlalchemy import create_engine, pool, text, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config.settings import settings

logger = logging.getLogger(__name__)


def _build_connect_args() -> dict:
    """Build SSL connect_args for Aiven cloud MySQL with defensive error handling."""
    if not settings.DB_SSL_CA:
        logger.debug("No SSL certificate configured (DB_SSL_CA not set)")
        return {}

    # Resolve path relative to backend root (two levels up from app/db/)
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    ca_path = os.path.join(backend_root, settings.DB_SSL_CA)
    
    logger.debug(f"SSL certificate path: {ca_path}")

    if not os.path.exists(ca_path):
        logger.warning(f"SSL CA file NOT found at: {ca_path} — attempting connection without SSL")
        return {}

    try:
        with open(ca_path, 'r') as f:
            cert_content = f.read()
            if "BEGIN CERTIFICATE" not in cert_content:
                logger.error(f"Invalid SSL certificate format at: {ca_path}")
                return {}
    except Exception as e:
        logger.error(f"Failed to read SSL certificate at {ca_path}: {e}")
        return {}

    logger.info(f"✓ SSL enabled — CA cert loaded")
    return {"ssl": {"ca": ca_path}}


def _build_engine():
    """Build the database engine with appropriate configuration for the environment."""
    if settings.DB_FALLBACK_SQLITE and not _can_reach_mysql():
        logger.warning(
            "MySQL %s:%s unreachable. Using SQLite fallback: %s",
            settings.DB_HOST,
            settings.DB_PORT,
            settings.SQLITE_DB_FILE,
        )
        return create_engine(
            settings.sqlite_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            echo=settings.DEBUG,
        )

    connect_args = _build_connect_args()
    
    # ── Serverless-optimized connection pooling ────────────────────────────────
    # Vercel/AWS Lambda: each invocation gets new process. Use NullPool:
    # - Creates fresh connection per request, closes immediately
    # - Prevents connection exhaustion and stale connections
    # - Standard practice for serverless/Lambda environments
    logger.info("✓ Database: MySQL with NullPool (serverless optimized)")
    
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,  # No pooling — fresh conn per request
        pool_pre_ping=True,       # Verify connection is alive before use
        echo=settings.DEBUG,      # log SQL queries in debug mode
    )
    
    # Add event listener for connection errors — log and continue
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        logger.debug("Database connection established")
    
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        logger.debug("Database connection checked out")
    
    return engine


def _can_reach_mysql(max_retries: int = 2) -> bool:
    """
    Return True only if MySQL can be reached and accepts a lightweight query.
    Retries on transient failures (network timeouts, etc).
    """
    for attempt in range(max_retries):
        connect_args = _build_connect_args()
        engine = create_engine(
            settings.database_url,
            connect_args={**connect_args, "connect_timeout": 3},
            poolclass=pool.NullPool,
            echo=False,
        )
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.debug(f"✓ MySQL connectivity check passed")
            return True
        except (socket.timeout, ConnectionRefusedError) as exc:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)  # exponential backoff: 0.5s, 1s
                logger.warning(f"MySQL connection attempt {attempt + 1} failed: {exc}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"MySQL connectivity test failed after {max_retries} attempts: {exc}")
        except Exception as exc:
            logger.warning(f"MySQL connectivity test failed: {exc}")
            return False
    
    return False


engine = _build_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency — yields a DB session per request.
    Includes retry logic for transient cloud database connection failures.
    """
    max_retries = 2
    db = None
    
    for attempt in range(max_retries + 1):
        try:
            db = SessionLocal()
            # Verify connection is alive before yielding
            db.execute(text("SELECT 1"))
            break
        except Exception as e:
            if db:
                try: db.close()
                except Exception: pass
                db = None
            if attempt < max_retries:
                time.sleep(0.3 * (attempt + 1))
                logger.warning(f"DB connection retry {attempt + 1}/{max_retries}: {type(e).__name__}")
            else:
                logger.error(f"DB connection failed after {max_retries + 1} attempts: {type(e).__name__}: {str(e)[:200]}")
                raise

    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"DB session error: {type(e).__name__}: {str(e)[:200]}")
        raise
    finally:
        db.close()
        logger.debug("DB session closed")
