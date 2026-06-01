"""
SQLAlchemy ORM model for the chat_messages table.
Each row is one message in a chat thread identified by the user's email.
sender: 'user' or 'admin'
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.db.database import Base
from app.db.time import utc_now_naive


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id         = Column(Integer, primary_key=True, autoincrement=True, index=True)
    email      = Column(String(255), nullable=False, index=True)   # thread key
    name       = Column(String(255), nullable=True)                # user's display name
    sender     = Column(String(10),  nullable=False)               # 'user' or 'admin'
    message    = Column(Text,        nullable=False)
    is_read    = Column(Boolean, default=False, nullable=False)    # unread for admin
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    def __repr__(self):
        return f"<ChatMessage id={self.id} email='{self.email}' sender={self.sender}>"
