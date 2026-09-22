# Dossier

Dossier is a live-source research and fact-checking agent. It breaks questions into checkable claims, searches the web, weighs evidence, and returns a cited report or structured JSON. The original private source prompt is intentionally not included in this public repository.

## Stack

- Next.js 16 App Router + React 19 + TypeScript frontend
- FastAPI + Uvicorn research API
- OpenAI Responses API with the built-in `web_search` tool
- Provider switching for OpenAI, DeepSeek, and local vLLM-compatible models
- Optional SearXNG adapter for live sources with DeepSeek and local models
- MySQL persistence for accounts, research runs, and source records, with memory fallback for local smoke tests
- In-memory request rate limiting for the unauthenticated first deployment

The API key stays on the FastAPI server. The browser only calls the Next.js `/api` proxy.

## Run locally

Prerequisites: Python 3.9+ and Node.js 20.9+.

### 1. Start the API

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export OPENAI_API_KEY='your-api-key'
# Production persistence and accounts:
export DATABASE_URL='mysql+pymysql://dossier:password@127.0.0.1:3306/dossier'
export DOSSIER_AUTH_SECRET='replace-with-a-long-random-secret'
dossier-web
```

For a local MySQL instance, copy `.env.example`, adjust any secrets, export it into the shell, and run:

```bash
cp .env.example .env
docker compose up -d mysql
set -a; source .env; set +a
dossier-web
```

The API runs at `http://127.0.0.1:8000`.

Deployment probes are available at `/api/health/live` and `/api/health/ready`; the latter checks the configured database connection.

Provider configuration:

```bash
# Default: DeepSeek hosted model
export MODEL_PROVIDER=deepseek
export DEEPSEEK_API_KEY='your-api-key'

# Hosted DeepSeek
export MODEL_PROVIDER=deepseek
export DEEPSEEK_API_KEY='your-api-key'

# Local vLLM / Qwen OpenAI-compatible server
export MODEL_PROVIDER=local
export LOCAL_MODEL_BASE_URL='http://127.0.0.1:8001/v1'
```

OpenAI uses the built-in web-search tool. DeepSeek and local models can use an independent SearXNG instance for live-source research:

```bash
export SEARXNG_URL='http://127.0.0.1:8080'
```

If `SEARXNG_URL` is not set, those providers still run as generation-only models and must label unsupported claims `UNVERIFIED`.

### 2. Start the Next.js frontend

In a second terminal:

```bash
cd frontend
npm ci
DOSSIER_API_URL='http://127.0.0.1:8000' npm run dev
```

Open [http://localhost:3000](http://localhost:3000). With `DATABASE_URL` configured, the interface shows account access, durable history, research progress, actionable errors, cited output, copy and Markdown/JSON download controls, and follow-up research. Without it, the app stays in lightweight session mode.

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

Set `OPENAI_API_KEY` and optionally `DOSSIER_MODEL` as server environment variables. For DeepSeek or local models, set the matching provider variables and optionally `SEARXNG_URL`. Do not commit secrets.

2. Frontend service: deploy `frontend/` on Vercel or another Next.js host. Build with `npm ci && npm run build`, start with `npm start`, and set `DOSSIER_API_URL` to the public API URL before building.

### MySQL and accounts

Set `DATABASE_URL` to a MySQL SQLAlchemy URL such as `mysql+pymysql://user:password@host:3306/dossier`. On startup, Dossier creates the initial `users`, `research_runs`, and `source_records` tables. The account endpoints are `/api/auth/signup`, `/api/auth/login`, and `/api/auth/me`; when a database is configured, research and history require a bearer session token by default. Set `DOSSIER_REQUIRE_AUTH=0` only for a controlled internal deployment.

Set `DOSSIER_AUTH_SECRET` to a long random value in every deployed API instance. The development fallback is intentionally not suitable for production. For a multi-instance deployment, replace the in-memory request limiter with a shared Redis or gateway limiter.

The first deployment also applies a small in-memory limit of 10 research requests per client per minute. Replace this with account-based quotas or a shared Redis limiter when scaling across multiple API instances.

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
