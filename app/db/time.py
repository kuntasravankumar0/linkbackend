"""Time helpers shared by SQLAlchemy models."""
from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Return naive UTC datetime values to preserve existing DB column behavior."""
    return datetime.now(UTC).replace(tzinfo=None)
