"""Optional MySQL persistence for users, research runs, and source records."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class StorageNotConfigured(RuntimeError):
    """Raised when a durable storage operation is requested without DATABASE_URL."""


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    research_runs: Mapped[list[ResearchRun]] = relationship(back_populates="user")


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    output_format: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(160))
    result_text: Mapped[str] = mapped_column(Text)
    response_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    follow_up_of: Mapped[Optional[int]] = mapped_column(ForeignKey("research_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    user: Mapped[User] = relationship(back_populates="research_runs", foreign_keys=[user_id])
    sources: Mapped[list[SourceRecord]] = relationship(
        back_populates="research_run", cascade="all, delete-orphan"
    )


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000))
    snippet: Mapped[str] = mapped_column(Text, default="")
    research_run: Mapped[ResearchRun] = relationship(back_populates="sources")


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configured_database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def database_configured() -> bool:
    return bool(configured_database_url())


def get_engine() -> Engine:
    global _engine
    url = configured_database_url()
    if not url:
        raise StorageNotConfigured("DATABASE_URL is not configured.")
    if _engine is None:
        _engine = create_engine(url, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _session_factory


def initialize_database() -> None:
    """Create the small initial schema; production migrations can replace this later."""

    Base.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def find_user(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.lower()))


def history_for_user(session: Session, user_id: int, limit: int) -> list[ResearchRun]:
    statement = (
        select(ResearchRun)
        .where(ResearchRun.user_id == user_id)
        .order_by(ResearchRun.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(statement).all())
