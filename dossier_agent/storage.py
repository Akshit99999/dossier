"""Small optional persistence layer for completed Dossier runs."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    output_format: Mapped[str] = mapped_column(String(16))
    result: Mapped[str] = mapped_column(Text)
    response_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def database_url() -> str | None:
    """Return the configured database URL, if persistence is enabled."""

    return os.getenv("DATABASE_URL") or None


def storage_configured() -> bool:
    return database_url() is not None


def _session_factory():
    url = database_url()
    if not url:
        return None
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def save_research_run(
    *, question: str, output_format: str, result: str, response_id: str | None
) -> None:
    """Persist a completed run when DATABASE_URL is configured."""

    factory = _session_factory()
    if factory is None:
        return
    with factory() as session:
        session.add(
            ResearchRun(
                question=question,
                output_format=output_format,
                result=result,
                response_id=response_id,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
