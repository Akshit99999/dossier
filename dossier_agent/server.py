"""FastAPI API server for the Dossier frontend."""

from __future__ import annotations

import os
from collections import deque
from datetime import datetime, timezone
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agent import DossierAgent, DossierError


app = FastAPI(title="Dossier", description="Live-source research and fact-checking agent")
recent_history: deque[dict] = deque(maxlen=50)


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    output_format: Literal["human", "json"] = "human"
    model: Optional[str] = Field(default=None, max_length=100)
    live_web: bool = True


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "dossier",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/api/history")
def history(limit: int = 20) -> dict[str, list[dict]]:
    safe_limit = max(1, min(limit, 50))
    return {"items": list(recent_history)[:safe_limit]}


@app.post("/api/research")
def research(request: ResearchRequest) -> dict:
    try:
        agent = DossierAgent(model=request.model or None, live_web=request.live_web)
        result = agent.research(request.question, output_format=request.output_format)
        payload: str | dict = result.text
        if request.output_format == "json":
            payload = result.as_json()
        recent_history.appendleft(
            {
                "id": len(recent_history) + 1,
                "question": request.question,
                "output_format": request.output_format,
                "response_id": result.response_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            "format": request.output_format,
            "result": payload,
            "response_id": result.response_id,
        }
    except (DossierError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY is not configured. Add it to the server environment and restart Dossier.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="The research service could not complete this request. Check the server logs and try again.",
        ) from exc


def main() -> None:
    uvicorn.run(
        "dossier_agent.server:app",
        host=os.getenv("DOSSIER_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", os.getenv("DOSSIER_PORT", "8000"))),
        reload=os.getenv("DOSSIER_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    main()
