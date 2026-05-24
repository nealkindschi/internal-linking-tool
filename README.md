# Internal Linking Tool

A local-first web tool that finds internal linking opportunities by cross-referencing Screaming Frog crawl data with Google Search Console query data.

## Prerequisites

- Python 3.10+ (3.9 works with warnings)
- Screaming Frog SEO Spider (licensed version for crawls >500 URLs)
- Google Search Console access (for GSC query data)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" google-api-python-client google-auth-oauthlib pandas beautifulsoup4 httpx pydantic jinja2 aiofiles
pip install pytest pytest-asyncio pytest-cov responses  # for development
```

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

## Architecture

Six core modules orchestrated by FastAPI:

| Module | Purpose |
|---|---|
| `sf_cli.py` | Screaming Frog CLI integration |
| `gsc_client.py` | Google Search Console API (OAuth) |
| `csv_parser.py` | Parse SF crawl exports |
| `page_fetcher.py` | Async HTTP content fetching |
| `match_engine.py` | Keyword matching + link exclusion |
| `anchor_engine.py` | Impression-weighted anchor suggestions |

## Development

```bash
python -m pytest tests/ -v
```
