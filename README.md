# Dossier

Dossier is a live-source research and fact-checking agent. It breaks questions into checkable claims, searches the web, weighs evidence, and returns a cited report or structured JSON. The original private source prompt is intentionally not included in this public repository.

## Stack

- Next.js 16 App Router + React 19 + TypeScript frontend
- FastAPI + Uvicorn research API
- OpenAI-compatible provider switching for OpenRouter, OpenAI, DeepSeek, and local vLLM-compatible models
- OpenRouter's `openrouter/free` router for online free-model testing
- Optional SearXNG adapter for live sources with DeepSeek and local models
- In-memory backend history for the lightweight first deployment
- In-memory request rate limiting

The API key stays on the FastAPI server. The browser only calls the Next.js `/api` proxy.

## Run locally

Prerequisites: Python 3.9+ and Node.js 20.9+.

### 1. Start the API

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export MODEL_PROVIDER=openrouter
export OPENROUTER_API_KEY='your-api-key'
export DOSSIER_MODEL=openrouter/free
dossier-web
```

The API runs at `http://127.0.0.1:8000`.

Deployment probes are available at `/api/health/live` and `/api/health/ready`; readiness reports the in-memory backend status.

Provider configuration:

```bash
# Default: OpenRouter free router
export MODEL_PROVIDER=openrouter
export OPENROUTER_API_KEY='your-api-key'
export DOSSIER_MODEL=openrouter/free

# DeepSeek hosted model (paid API usage may apply)
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

Open [http://localhost:3000](http://localhost:3000). The interface shows provider status, research progress, actionable errors, cited output, copy and Markdown/JSON download controls, follow-up research, and recent topics from the running backend session.

## CLI usage

```bash
dossier "Is the claim that coffee dehydrates you supported by current evidence?"
dossier --format json "What changed in India's data-protection rules in 2026?"
```

Use `--no-web` for offline testing. Unsupported claims should then be marked unverified.

## Why output may not appear

If the result panel reports that the API key is needed, set the selected provider key in the same terminal that starts `dossier-web`, then restart the API. Check the API directly with:

```bash
curl http://127.0.0.1:8000/api/health
```

The response includes the selected provider and whether it is configured. A real research request requires credentials for hosted providers.

## Deploy simply

Deploy the two services separately:

1. API service: deploy the repository root on Railway, Render, or another Python host. Start command:

   ```bash
   uvicorn dossier_agent.server:app --host 0.0.0.0 --port $PORT
   ```

Set the selected provider variables and optionally `SEARXNG_URL` as server environment variables. Do not commit secrets.

2. Frontend service: deploy `frontend/` on Vercel or another Next.js host. Build with `npm ci && npm run build`, start with `npm start`, and set `DOSSIER_API_URL` to the public API URL before building.

The first deployment keeps history in the API process. For multi-instance deployments, use a shared persistence and rate-limit service when you are ready to add them.

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

OpenRouter free models are intended for testing and have provider-dependent rate limits and availability. Create a key at [OpenRouter Keys](https://openrouter.ai/keys), keep it only on the API server, and use a paid model only when you need higher limits or more consistent production behavior. High-stakes decisions should be independently verified.

## License

MIT
