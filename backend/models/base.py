"""SQLAlchemy base model and mixins."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
