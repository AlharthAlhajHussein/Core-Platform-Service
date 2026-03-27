import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy Models."""
    pass

class BaseModel(Base):
    """An abstract base model providing common fields like id and created_at."""
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )