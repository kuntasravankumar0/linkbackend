"""
SQLAlchemy ORM model for the contact_messages table.
Stores messages submitted via the Contact page.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SAEnum
from app.db.database import Base
from app.db.time import utc_now_naive


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id         = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name       = Column(String(255), nullable=False)
    email      = Column(String(255), nullable=False)
    phone      = Column(String(30),  nullable=True)
    subject    = Column(String(255), nullable=True)
    message    = Column(Text,        nullable=False)

    # Admin can mark as read / archived
    is_read    = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    def __repr__(self):
        return f"<ContactMessage id={self.id} from='{self.email}' read={self.is_read}>"
