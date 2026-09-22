# Dossier

Dossier is a live-source research and fact-checking agent. It breaks questions into checkable claims, searches the web, weighs evidence, and returns a cited report or structured JSON. The original private source prompt is intentionally not included in this public repository.

## Stack

- Next.js 16 App Router + React 19 + TypeScript frontend
- FastAPI + Uvicorn research API
- OpenAI Responses API with the built-in `web_search` tool
- Provider switching for OpenAI, DeepSeek, and local vLLM-compatible models
- Optional in-memory session history (MySQL is not required right now)

The API key stays on the FastAPI server. The browser only calls the Next.js `/api` proxy.

## Run locally

Prerequisites: Python 3.9+ and Node.js 20.9+.

### 1. Start the API

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export OPENAI_API_KEY='your-api-key'
dossier-web
```

The API runs at `http://127.0.0.1:8000`.

Provider configuration:

```bash
# Default: OpenAI with native web search
export MODEL_PROVIDER=openai
export OPENAI_API_KEY='your-api-key'

# Hosted DeepSeek
export MODEL_PROVIDER=deepseek
export DEEPSEEK_API_KEY='your-api-key'

# Local vLLM / Qwen OpenAI-compatible server
export MODEL_PROVIDER=local
export LOCAL_MODEL_BASE_URL='http://127.0.0.1:8001/v1'
```

OpenAI is the only provider currently connected to the built-in web-search tool. DeepSeek and local models work for model generation; an independent search adapter will be added before using them for live-source research.

### 2. Start the Next.js frontend

In a second terminal:

```bash
cd frontend
npm ci
DOSSIER_API_URL='http://127.0.0.1:8000' npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The interface shows connection/API-key status, research progress, actionable errors, cited output, copy controls, and recent topics from the current API session.

## CLI usage

```bash
dossier "Is the claim that coffee dehydrates you supported by current evidence?"
dossier --format json "What changed in India's data-protection rules in 2026?"
```

Use `--no-web` for offline testing. Unsupported claims should then be marked unverified.

## Why output may not appear

If the result panel reports that the API key is needed, set `OPENAI_API_KEY` in the same terminal that starts `dossier-web`, then restart the API. Check the API directly with:

```bash
curl http://127.0.0.1:8000/api/health
```

The response includes `openai_configured`. A real research request also requires an OpenAI API key with access to the selected model and web search.

## Deploy simply

Deploy the two services separately:

1. API service: deploy the repository root on Railway, Render, or another Python host. Start command:

   ```bash
   uvicorn dossier_agent.server:app --host 0.0.0.0 --port $PORT
   ```

   Set `OPENAI_API_KEY` and optionally `DOSSIER_MODEL` as server environment variables. Do not commit them.

2. Frontend service: deploy `frontend/` on Vercel or another Next.js host. Build with `npm ci && npm run build`, start with `npm start`, and set `DOSSIER_API_URL` to the public API URL before building.

MySQL is deliberately not part of the first deployment: history is session-only, which keeps the initial launch small. Add MySQL later when persistent accounts, research history, and audit logs are needed.

## Project layout

```text
dossier_agent/           Python API, CLI, and research agent
frontend/app/            Next.js App Router pages and styles
frontend/next.config.ts  API proxy configuration
tests/                   Python API and agent tests
```

## Verification

```bash
pytest
cd frontend && npm run typecheck && npm run build
```

Research requests use the OpenAI API and may incur API and web-search charges. High-stakes decisions should be independently verified.

## License

MIT
