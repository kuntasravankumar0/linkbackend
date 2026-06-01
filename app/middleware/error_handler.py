"""
Global exception handlers.
All errors return: { "message": "...", "errors": {...} | null, "error_id": "uuid" }
This matches exactly what the frontend reads:
  error.response?.data?.message
  error.response?.data?.errors
  error.response?.data?.error_id (for support/debugging)
"""
import logging
import uuid
from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic v2 validation errors → field-level error map."""
    errors = {}
    for error in exc.errors():
        # Build a clean field path, skip 'body' prefix
        loc = [str(l) for l in error["loc"] if l != "body"]
        field = ".".join(loc) if loc else "unknown"
        errors[field] = error["msg"].replace("Value error, ", "")

    logger.warning(f"Validation error on {request.method} {request.url.path}: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"message": "Validation failed. Please check your input.", "errors": errors},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """FastAPI HTTPException — pass through detail dict or wrap string."""
    detail = exc.detail
    if isinstance(detail, dict):
        content = detail
    else:
        content = {"message": str(detail), "errors": None}

    logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {detail}")
    return JSONResponse(status_code=exc.status_code, content=content)


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Database errors — log full detail with context, return safe message to client."""
    error_id = str(uuid.uuid4())
    error_msg = str(exc)
    
    # Log the actual error for debugging with correlation ID
    logger.error(
        f"Database error [ID: {error_id}] on {request.method} {request.url.path}",
        exc_info=True,
        extra={
            "error_id": error_id,
            "error_type": type(exc).__name__,
            "error_details": error_msg[:500],  # Limit length for logs
            "url": str(request.url),
            "method": request.method,
        }
    )
    
    # Return safe message to client with correlation ID (don't expose DB details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "A database error occurred. Please try again.",
            "error_id": error_id,  # User can provide this for support
            "errors": None,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors."""
    logger.error(f"Unexpected error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "An unexpected server error occurred.", "errors": None},
    )
