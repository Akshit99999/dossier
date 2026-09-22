"""Small optional persistence layer for completed Dossier runs."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    output_format: Mapped[str] = mapped_column(String(16))
    result: Mapped[str] = mapped_column(Text)
    response_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
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


def list_recent_runs(limit: int = 20) -> list[dict[str, str | int | None]]:
    """Return the most recent research topics for the history panel."""

    factory = _session_factory()
    if factory is None:
        return []
    safe_limit = max(1, min(limit, 100))
    with factory() as session:
        runs = session.scalars(
            select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(safe_limit)
        ).all()
        return [
            {
                "id": run.id,
                "question": run.question,
                "output_format": run.output_format,
                "response_id": run.response_id,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ]
