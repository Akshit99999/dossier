# Dossier

Dossier is a command-line deep-research and fact-checking agent. The original private source prompt is intentionally not included in this public repository.

It uses the OpenAI Responses API with the built-in web-search tool, then produces either a cited human-readable report or the JSON format defined by the research workflow.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export OPENAI_API_KEY='your-api-key'
```

`OPENAI_API_KEY` is required. The default model is `gpt-5.5`; set `DOSSIER_MODEL` or pass `--model` to use another model available to your account. To use a private local system prompt, set `DOSSIER_SYSTEM_PROMPT_PATH`; files under `prompts/` are ignored by Git.

## Usage

Human-readable report:

```bash
dossier "Is the claim that coffee dehydrates you supported by current evidence?"
```

Machine-readable JSON:

```bash
dossier --format json "What changed in India's data-protection rules in 2026?"
```

Browser frontend:

```bash
python -m pip install -e '.[dev]'
dossier-web
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The frontend sends requests to the local FastAPI server and never exposes your API key to the browser.

The `--no-web` option is available for testing or environments where live search is unavailable. In that mode, the agent instructs the model to mark claims as unverified unless supported by the available context.

## Project layout

```text
dossier_agent/  Python package, CLI, and web server
web/            Browser frontend
tests/          Offline unit tests
```

## Development

```bash
pytest
```

Research requests use the OpenAI API and may incur API and web-search charges. The application does not store responses locally; the API's own data-retention settings apply.

## License

MIT
