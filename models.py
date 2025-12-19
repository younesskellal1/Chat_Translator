"""Database models and initialization."""

import os
import datetime as dt
from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash


class Base(DeclarativeBase):
    pass


# Database setup
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    id: int = Column(Integer, primary_key=True)
    name: str = Column(String(120), nullable=False)
    email: str = Column(String(255), nullable=False, unique=True, index=True)
    password_hash: str = Column(String(255), nullable=False)
    created_at: dt.datetime = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint('email', name='uq_users_email'),
    )

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for secure storage."""
        return generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, password)


class ChatSession(Base):
    """Chat session model for storing conversation sessions."""
    __tablename__ = "chat_sessions"
    id: str = Column(String(50), primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title: str = Column(String(200), nullable=False, default="New chat")
    archived: bool = Column(Integer, nullable=False, default=False)
    created_at: dt.datetime = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at: dt.datetime = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)


class ChatMessage(Base):
    """Chat message model for storing individual messages."""
    __tablename__ = "chat_messages"
    id: int = Column(Integer, primary_key=True)
    session_id: str = Column(String(50), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: str = Column(String(20), nullable=False)  # 'user', 'assistant', 'system', 'error'
    text: str = Column(Text, nullable=False)
    created_at: dt.datetime = Column(DateTime, default=dt.datetime.utcnow, nullable=False)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=ENGINE)


def get_db():
    """Get database session."""
    return SessionLocal()
