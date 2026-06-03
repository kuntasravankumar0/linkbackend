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
    connect_args = {
        "connect_timeout": 15,
        "read_timeout": 20,
        "write_timeout": 20,
        "charset": "utf8mb4",
    }

    if not settings.DB_SSL_CA:
        logger.debug("No SSL certificate configured (DB_SSL_CA not set)")
        return connect_args

    # Resolve path relative to backend root (two levels up from app/db/)
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    ca_path = os.path.join(backend_root, settings.DB_SSL_CA)
    
    logger.info(f"SSL certificate path (computed): {ca_path}")
    logger.info(f"Backend root: {backend_root}")

    if not os.path.exists(ca_path):
        # Try alternative paths for different deployment environments
        alt_ca_paths = [
            "/vercel/path0/ssl/ca.pem",  # Vercel serverless
            os.path.abspath(ca_path),     # Absolute version of computed path
        ]
        
        # Aiven requires SSL — must find certificate
        logger.warning(f"Primary SSL path not found: {ca_path}")
        logger.info(f"Trying {len(alt_ca_paths)} alternative paths...")
        
        found = False
        for alt_path in alt_ca_paths:
            logger.debug(f"Checking: {alt_path}")
            if os.path.exists(alt_path):
                ca_path = alt_path
                found = True
                logger.info(f"✓ Found SSL cert at alternative path: {alt_path}")
                break
        
        if not found:
            logger.error(f"CRITICAL: SSL CA file NOT found at any location")
            logger.error(f"Checked paths: {[ca_path] + alt_ca_paths}")
            logger.error(f"Aiven requires SSL. Database connection will fail.")
            # Try with just ssl=True flag (some drivers find cert in system store)
            connect_args["ssl"] = True
            return connect_args

    try:
        with open(ca_path, 'r') as f:
            cert_content = f.read()
            if "BEGIN CERTIFICATE" not in cert_content:
                logger.error(f"Invalid SSL certificate format at: {ca_path}")
                return connect_args
            logger.info(f"✓ SSL certificate validated — {len(cert_content)} bytes")
    except Exception as e:
        logger.error(f"Failed to read SSL certificate at {ca_path}: {e}")
        return connect_args

    logger.info(f"✓ SSL enabled for Aiven — CA cert loaded from: {ca_path}")
    connect_args["ssl"] = {"ca": ca_path}
    return connect_args


def _build_engine():
    """Build the database engine with appropriate configuration for the environment."""
    if settings.DB_FALLBACK_SQLITE:
        if not _can_reach_mysql():
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
    elif os.getenv("VERCEL"):
        logger.info("VERCEL environment detected and SQLite fallback is disabled.")

    connect_args = _build_connect_args()
    
    # ── Serverless-optimized connection pooling ────────────────────────────────
    # Vercel/AWS Lambda: each invocation gets new process. Use NullPool:
    # - Creates fresh connection per request, closes immediately
    # - Prevents connection exhaustion and stale connections
    # - Standard practice for serverless/Lambda environments
    logger.info("✓ Database: MySQL with NullPool (Vercel serverless)")
    logger.info(f"Connection URL: mysql+pymysql://{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info(f"Connect args: timeout={connect_args.get('connect_timeout')}s, SSL={'enabled' if 'ssl' in connect_args else 'disabled'}")
    
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        poolclass=NullPool,  # Vercel serverless — new connection per request
        pool_pre_ping=True,
        echo=settings.DEBUG,
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
        # PyMySQL needs connect_timeout inside connect_args dict
        connect_args["connect_timeout"] = 8
        engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            poolclass=pool.NullPool,
            echo=False,
        )
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.debug(f"✓ MySQL connectivity check passed")
            return True
        except Exception as exc:
            logger.warning(f"MySQL connectivity test attempt {attempt + 1} failed: {type(exc).__name__}: {str(exc)[:120]}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
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
