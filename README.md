# Internal Linking Tool

A local-first web tool that finds internal linking opportunities by cross-referencing Screaming Frog crawl data with Google Search Console query data. Generates descriptive anchor text using DeepSeek V4 Pro LLM (with heuristic fallback).

## Prerequisites

- Python 3.10+ (3.9 works with warnings)
- Screaming Frog SEO Spider (licensed version for crawls >500 URLs)
- Google Search Console access (for GSC query data)
- DeepSeek API key (optional, for LLM-powered anchor text; tool works without it)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" google-api-python-client google-auth-oauthlib pandas beautifulsoup4 httpx pydantic jinja2 aiofiles openai
pip install pytest pytest-asyncio pytest-cov responses  # for development
```

### DeepSeek API Key (LLM Anchor Text)

For descriptive, LLM-generated anchor text instead of raw keywords:

```bash
export DEEPSEEK_API_KEY="sk-your-key-here"
```

Add this to your `~/.zshrc` for persistence. Without it, the tool falls back to heuristic anchor text based on the target page title, H1, and slug.

### GSC Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Search Console API
3. Create OAuth 2.0 credentials (Desktop application type)
4. Download the JSON and save to `~/.config/internal-linking-tool/gsc_credentials.json`

### Screaming Frog Path (optional)

If Screaming Frog is not at the default macOS path, set:
```bash
export SF_CLI_PATH="/path/to/ScreamingFrogSEOSpiderLauncher"
```

## Usage

```bash
cd internal_linking_tool
source .venv/bin/activate
python -m internal_linking_tool.main
```

Open **http://localhost:8765** in your browser.

1. Enter the target URL you want to build links to
2. Select an existing Screaming Frog crawl or start a new one
3. Wait for analysis to complete
4. Browse, filter, sort, and export the opportunities

### Results Dashboard

- **Pages w/ Opps**: Number of source pages with linking opportunities
- **Anchor Matches**: Total individual keyword matches across all pages
- **Auth (ⓘ)**: Link Authority from Screaming Frog (0-100); hover for details
- **Best Anchor**: Primary recommended anchor text (LLM or heuristic)
- **Copy button**: One-click copy of any anchor text to clipboard
- **Metadata bar**: Shows target page title, keyword list, GSC status, and generation method

## Architecture

Seven core modules orchestrated by FastAPI:

| Module | Purpose |
|---|--|
| `sf_cli.py` | Screaming Frog CLI integration |
| `gsc_client.py` | Google Search Console API (OAuth) |
| `csv_parser.py` | Parse SF crawl exports |
| `page_fetcher.py` | Async HTTP content fetching + metadata extraction |
| `match_engine.py` | Keyword matching + link exclusion + opportunity scoring |
| `anchor_engine.py` | LLM-powered + heuristic fallback anchor text generation |
| `llm_client.py` | OpenAI-compatible client for DeepSeek V4 Pro |

## Anchor Text Generation

The tool generates anchor text in two modes:

| Mode | How it works | When |
|------|-------------|------|
| **LLM (DeepSeek)** | Sends target page metadata (title, H1, slug) + GSC keywords + source sentence context to DeepSeek V4 Pro. Returns up to 3 descriptive, natural anchor variations per match. | `DEEPSEEK_API_KEY` is set |
| **Heuristic** | Uses target page title as primary anchor, H1 and slug as variations. Falls back to cleaned GSC keyword if no metadata available. | No API key or LLM unavailable |

Anchor text follows SEO best practices: descriptive of the target page, 2-5 words, natural-sounding, never generic ("click here", "read more").

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | (none) | DeepSeek API key for LLM anchor text |
| `LLM_ENABLED` | `true` | Set to `false` to disable LLM and use heuristic only |
| `LLM_ENDPOINT` | `https://api.deepseek.com/v1` | API endpoint (supports any OpenAI-compatible API) |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `SF_CLI_PATH` | macOS default | Path to Screaming Frog CLI binary |
| `GSC_CREDENTIALS_PATH` | `~/.config/internal-linking-tool/gsc_credentials.json` | GSC OAuth credentials |
| `GSC_TOKEN_PATH` | `~/.config/internal-linking-tool/gsc_token.json` | GSC OAuth token cache |

## Development

```bash
python -m pytest tests/ -v
```
