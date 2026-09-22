"""FastAPI API server for the Dossier frontend."""

from __future__ import annotations

import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from .agent import DossierAgent, DossierError
from .auth import (
    AuthIdentity,
    AuthenticationError,
    hash_password,
    issue_token,
    normalize_email,
    read_token,
    verify_password,
)
from .database import (
    ResearchRun,
    SourceRecord,
    StorageNotConfigured,
    User,
    database_configured,
    find_user,
    history_for_user,
    initialize_database,
    session_scope,
)
from .providers import resolve_provider


app = FastAPI(title="Dossier", description="Live-source research and fact-checking agent")
recent_history: deque[dict] = deque(maxlen=50)
research_rate_windows: dict[str, deque[float]] = {}
_database_initialized = False
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60.0


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    output_format: Literal["human", "json"] = "human"
    model: Optional[str] = Field(default=None, max_length=100)
    provider: Optional[str] = Field(default=None, max_length=32)
    live_web: bool = True
    follow_up_of: Optional[int] = None


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


@app.get("/api/health")
def health() -> dict[str, object]:
    try:
        config = resolve_provider()
        provider_name = config.name
        model = config.model
        provider_configured = config.api_key_configured
    except ValueError:
        provider_name = "unknown"
        model = None
        provider_configured = False
    return {
        "status": "ok",
        "service": "dossier",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "provider": provider_name,
        "model": model,
        "provider_configured": provider_configured,
        "database_configured": database_configured(),
        "auth_required": auth_required(),
        "auth_secret_configured": bool(os.getenv("DOSSIER_AUTH_SECRET")),
    }


@app.get("/api/history")
def history(http_request: Request, limit: int = 20) -> dict[str, list[dict]]:
    safe_limit = max(1, min(limit, 50))
    identity = optional_identity(http_request)
    if auth_required() and identity is None:
        raise HTTPException(status_code=401, detail="Sign in to view persistent research history.")
    if identity and database_configured():
        try:
            ensure_database()
            with session_scope() as session:
                return {"items": [history_item(run) for run in history_for_user(session, identity.user_id, safe_limit)]}
        except (StorageNotConfigured, SQLAlchemyError) as exc:
            raise HTTPException(status_code=503, detail="Persistent history is unavailable right now.") from exc
    return {"items": list(recent_history)[:safe_limit]}


@app.post("/api/auth/signup")
def signup(request: AuthRequest) -> dict[str, object]:
    require_database()
    try:
        email = normalize_email(request.email)
        ensure_database()
        with session_scope() as session:
            if find_user(session, email):
                raise HTTPException(status_code=409, detail="An account with that email already exists.")
            user = User(email=email, password_hash=hash_password(request.password))
            session.add(user)
            session.flush()
            identity = AuthIdentity(user_id=user.id, email=user.email)
            return {"token": issue_token(identity), "user": {"id": user.id, "email": user.email}}
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="The account service is unavailable right now.") from exc


@app.post("/api/auth/login")
def login(request: AuthRequest) -> dict[str, object]:
    require_database()
    try:
        email = normalize_email(request.email)
        ensure_database()
        with session_scope() as session:
            user = find_user(session, email)
            if user is None or not verify_password(request.password, user.password_hash):
                raise HTTPException(status_code=401, detail="Email or password is incorrect.")
            identity = AuthIdentity(user_id=user.id, email=user.email)
            return {"token": issue_token(identity), "user": {"id": user.id, "email": user.email}}
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="The account service is unavailable right now.") from exc


@app.get("/api/auth/me")
def me(http_request: Request) -> dict[str, object]:
    identity = require_identity(http_request)
    return {"user": {"id": identity.user_id, "email": identity.email}}


def enforce_rate_limit(request: Request) -> None:
    """Keep unauthenticated deployments safe until account quotas exist."""

    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = research_rate_windows.setdefault(client_key, deque())
    while window and now - window[0] >= RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Research rate limit reached. Please wait a minute and try again.",
        )
    window.append(now)


def auth_required() -> bool:
    configured = os.getenv("DOSSIER_REQUIRE_AUTH")
    return database_configured() and configured != "0"


def ensure_database() -> None:
    global _database_initialized
    if not database_configured():
        raise StorageNotConfigured("DATABASE_URL is not configured.")
    if not _database_initialized:
        initialize_database()
        _database_initialized = True


def require_database() -> None:
    if not database_configured():
        raise HTTPException(
            status_code=503,
            detail="Database-backed accounts require DATABASE_URL. Configure MySQL and restart Dossier.",
        )


def optional_identity(http_request: Request) -> Optional[AuthIdentity]:
    header = http_request.headers.get("authorization", "")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Use a Bearer session token.")
    try:
        return read_token(token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_identity(http_request: Request) -> AuthIdentity:
    identity = optional_identity(http_request)
    if identity is None:
        raise HTTPException(status_code=401, detail="Sign in to use this feature.")
    return identity


def history_item(run: ResearchRun) -> dict[str, object]:
    return {
        "id": run.id,
        "question": run.question,
        "output_format": run.output_format,
        "response_id": run.response_id,
        "provider": run.provider,
        "created_at": run.created_at.isoformat(),
        "source_count": len(run.sources),
    }


@app.post("/api/research")
def research(request: ResearchRequest, http_request: Request) -> dict:
    enforce_rate_limit(http_request)
    identity = optional_identity(http_request)
    if auth_required() and identity is None:
        raise HTTPException(status_code=401, detail="Sign in before starting research.")
    try:
        agent = DossierAgent(
            model=request.model or None,
            provider=request.provider or None,
            live_web=request.live_web,
        )
        result = agent.research(request.question, output_format=request.output_format)
        payload: str | dict = result.text
        if request.output_format == "json":
            payload = result.as_json()
        persisted_research_id: Optional[int] = None
        if identity and database_configured():
            ensure_database()
            with session_scope() as session:
                run = ResearchRun(
                    user_id=identity.user_id,
                    question=request.question,
                    output_format=request.output_format,
                    provider=agent.provider_config.name,
                    model=agent.model,
                    result_text=result.text,
                    response_id=result.response_id,
                    follow_up_of=request.follow_up_of,
                )
                session.add(run)
                session.flush()
                persisted_research_id = run.id
                for position, url in enumerate(extract_urls(result.text), start=1):
                    session.add(
                        SourceRecord(
                            research_run_id=run.id,
                            position=position,
                            title=f"Referenced source {position}",
                            url=url,
                        )
                    )
        recent_history.appendleft(
            {
                "id": len(recent_history) + 1,
                "question": request.question,
                "output_format": request.output_format,
                "response_id": result.response_id,
                "provider": agent.provider_config.name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            "format": request.output_format,
            "result": payload,
            "response_id": result.response_id,
            "research_id": persisted_research_id,
        }
    except (DossierError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (StorageNotConfigured, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="The persistent research service is unavailable right now.") from exc
    except Exception as exc:
        try:
            config = resolve_provider(request.provider, request.model)
        except ValueError:
            config = None
        if config and not config.api_key_configured:
            key_name = {
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
            }.get(config.name, "the provider credential")
            raise HTTPException(
                status_code=503,
                detail=f"{config.name.title()} is not configured. Add {key_name} to the server environment and restart Dossier.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="The research service could not complete this request. Check the server logs and try again.",
        ) from exc


@app.get("/api/research/{research_id}")
def research_detail(research_id: int, http_request: Request) -> dict[str, object]:
    identity = require_identity(http_request)
    require_database()
    try:
        ensure_database()
        with session_scope() as session:
            run = session.get(ResearchRun, research_id)
            if run is None or run.user_id != identity.user_id:
                raise HTTPException(status_code=404, detail="Research run not found.")
            return {
                "id": run.id,
                "question": run.question,
                "result": run.result_text,
                "provider": run.provider,
                "model": run.model,
                "created_at": run.created_at.isoformat(),
                "sources": [
                    {
                        "id": source.id,
                        "position": source.position,
                        "title": source.title,
                        "url": source.url,
                        "snippet": source.snippet,
                    }
                    for source in run.sources
                ],
            }
    except HTTPException:
        raise
    except (StorageNotConfigured, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Persistent research is unavailable right now.") from exc


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for candidate in re.findall(r"https?://[^\s)\]>]+", text):
        url = candidate.rstrip(".,;:")
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= 20:
            break
    return urls


def main() -> None:
    uvicorn.run(
        "dossier_agent.server:app",
        host=os.getenv("DOSSIER_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", os.getenv("DOSSIER_PORT", "8000"))),
        reload=os.getenv("DOSSIER_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    main()
