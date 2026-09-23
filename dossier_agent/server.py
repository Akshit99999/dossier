"""FastAPI API server for the Dossier frontend with durable auth and history."""

from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .agent import DossierAgent, DossierError
from .db import (
    User,
    authenticate_user,
    delete_session,
    get_db_connection,
    get_user_by_token,
    init_db,
    register_user,
)
from .providers import resolve_provider


app = FastAPI(title="Dossier", description="Live-source research and fact-checking agent")
recent_history: deque[dict] = deque(maxlen=50)
research_rate_windows: dict[str, deque[float]] = {}
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60.0

# Initialize database tables on server module load
init_db()


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    output_format: Literal["human", "json"] = "human"
    depth: Literal["surface", "deep", "phd", "soul_shattering"] = "deep"
    model: Optional[str] = Field(default=None, max_length=100)
    provider: Optional[str] = Field(default=None, max_length=32)
    live_web: bool = True
    follow_up_of: Optional[int] = None


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


def get_current_user_from_header(authorization: Optional[str]) -> Optional[User]:
    """Helper to parse Bearer token from authorization header and resolve User."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split("Bearer ", 1)[1].strip()
    return get_user_by_token(token)


@app.post("/api/auth/register")
def register(request: RegisterRequest) -> dict:
    try:
        user = register_user(request.email, request.password)
        _, token = authenticate_user(request.email, request.password)
        return {
            "status": "ok",
            "user": {"id": user.id, "email": user.email, "created_at": user.created_at},
            "token": token,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/login")
def login(request: LoginRequest) -> dict:
    try:
        user, token = authenticate_user(request.email, request.password)
        return {
            "status": "ok",
            "user": {"id": user.id, "email": user.email, "created_at": user.created_at},
            "token": token,
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/auth/me")
def me(authorization: Optional[str] = Header(None)) -> dict:
    user = get_current_user_from_header(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": {"id": user.id, "email": user.email, "created_at": user.created_at}}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)) -> dict:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        delete_session(token)
    return {"status": "ok"}


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
    }


@app.get("/api/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "dossier"}


@app.get("/api/health/ready")
def readiness() -> dict[str, object]:
    return {"status": "ready", "storage": "sqlite", "service": "dossier"}


@app.get("/api/history")
def history(
    limit: int = 20,
    authorization: Optional[str] = Header(None),
) -> dict[str, list[dict]]:
    safe_limit = max(1, min(limit, 50))
    user = get_current_user_from_header(authorization)

    conn = get_db_connection()
    try:
        if user:
            rows = conn.execute(
                """
                SELECT id, question, output_format, response_id, provider, model, result, sources, follow_up_of, created_at
                FROM research_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user.id, safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, question, output_format, response_id, provider, model, result, sources, follow_up_of, created_at
                FROM research_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        items = []
        for r in rows:
            sources_list = json.loads(r["sources"]) if r["sources"] else []
            items.append(
                {
                    "id": r["id"],
                    "question": r["question"],
                    "output_format": r["output_format"],
                    "response_id": r["response_id"],
                    "provider": r["provider"],
                    "model": r["model"],
                    "result": r["result"],
                    "sources": sources_list,
                    "follow_up_of": r["follow_up_of"],
                    "created_at": r["created_at"],
                }
            )
        # If DB is empty, fallback to recent in-memory items
        if not items and recent_history:
            return {"items": list(recent_history)[:safe_limit]}
        return {"items": items}
    finally:
        conn.close()


def enforce_rate_limit(request: Request) -> None:
    """Keep the lightweight deployment safe from accidental bursts."""
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


@app.post("/api/research")
def research(
    request: ResearchRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None),
) -> dict:
    enforce_rate_limit(http_request)
    user = get_current_user_from_header(authorization)
    try:
        agent = DossierAgent(
            model=request.model or None,
            provider=request.provider or None,
            live_web=request.live_web,
        )
        result = agent.research(
            request.question,
            output_format=request.output_format,
            depth=request.depth,
        )
        payload: str | dict = result.text
        if request.output_format == "json":
            payload = result.as_json()
        source_urls = extract_urls(result.text)

        # Persist to SQLite database
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        history_id: int
        try:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO research_history (
                        user_id, question, output_format, response_id, provider, model, result, sources, follow_up_of, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.id if user else None,
                        request.question,
                        request.output_format,
                        result.response_id,
                        agent.provider_config.name,
                        agent.model,
                        result.text,
                        json.dumps(source_urls),
                        request.follow_up_of,
                        now_iso,
                    ),
                )
                history_id = cursor.lastrowid
        finally:
            conn.close()

        recent_history.appendleft(
            {
                "id": history_id,
                "question": request.question,
                "output_format": request.output_format,
                "response_id": result.response_id,
                "provider": agent.provider_config.name,
                "model": agent.model,
                "result": result.text,
                "sources": source_urls,
                "follow_up_of": request.follow_up_of,
                "created_at": now_iso,
            }
        )
        return {
            "format": request.output_format,
            "result": payload,
            "response_id": result.response_id,
            "research_id": history_id,
        }
    except (DossierError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
