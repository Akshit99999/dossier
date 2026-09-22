"""FastAPI server for the Dossier browser frontend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import DossierAgent, DossierError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"

app = FastAPI(title="Dossier", description="Live-source research and fact-checking agent")
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    output_format: Literal["human", "json"] = "human"
    model: str | None = Field(default=None, max_length=100)
    live_web: bool = True


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dossier"}


@app.post("/api/research")
def research(request: ResearchRequest) -> dict:
    try:
        agent = DossierAgent(model=request.model or None, live_web=request.live_web)
        result = agent.research(request.question, output_format=request.output_format)
        payload: str | dict = result.text
        if request.output_format == "json":
            payload = result.as_json()
        return {
            "format": request.output_format,
            "result": payload,
            "response_id": result.response_id,
        }
    except (DossierError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Research service failed.") from exc


def main() -> None:
    uvicorn.run(
        "dossier_agent.server:app",
        host=os.getenv("DOSSIER_HOST", "127.0.0.1"),
        port=int(os.getenv("DOSSIER_PORT", "8000")),
        reload=os.getenv("DOSSIER_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    main()
