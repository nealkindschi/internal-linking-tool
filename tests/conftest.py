"""Shared test fixtures for the Internal Linking Tool."""

import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_crawl_csv() -> str:
    path = FIXTURES_DIR / "sample_crawl.csv"
    if not path.exists():
        pytest.skip("Sample crawl CSV not found")
    return str(path)


@pytest.fixture
def sample_crawl_data() -> list[dict]:
    return [
        {
            "URL": "https://example.com/blog/solar-panel-guide-2024",
            "Status Code": "200",
            "Link Score": "94",
            "Unique Inlinks": "45",
            "Outlinks": "https://example.com/about/,https://example.com/blog/wind-power-basics",
            "GSC Clicks": "1240",
        },
        {
            "URL": "https://example.com/blog/wind-power-basics",
            "Status Code": "200",
            "Link Score": "87",
            "Unique Inlinks": "32",
            "Outlinks": "https://example.com/about/",
            "GSC Clicks": "890",
        },
        {
            "URL": "https://example.com/404-page",
            "Status Code": "404",
            "Link Score": "0",
            "Unique Inlinks": "0",
            "Outlinks": "",
            "GSC Clicks": "0",
        },
        {
            "URL": "https://example.com/redirected-page",
            "Status Code": "301",
            "Link Score": "0",
            "Unique Inlinks": "5",
            "Outlinks": "",
            "GSC Clicks": "0",
        },
    ]


@pytest.fixture
def sample_gsc_response() -> dict:
    return {
        "rows": [
            {"keys": ["renewable energy solutions", "/target/"], "clicks": 450, "impressions": 5200, "ctr": 0.086, "position": 3.2},
            {"keys": ["sustainable power", "/target/"], "clicks": 280, "impressions": 3100, "ctr": 0.090, "position": 4.1},
            {"keys": ["green energy", "/target/"], "clicks": 190, "impressions": 2400, "ctr": 0.079, "position": 5.8},
            {"keys": ["clean energy solutions", "/target/"], "clicks": 120, "impressions": 1800, "ctr": 0.067, "position": 7.3},
        ],
        "responseAggregationType": "byPage",
    }


@pytest.fixture
def sample_gsc_rows(sample_gsc_response) -> list[dict]:
    return [
        {"query": r["keys"][0], "page": r["keys"][1], "clicks": r["clicks"], "impressions": r["impressions"]}
        for r in sample_gsc_response["rows"]
    ]


@pytest.fixture
def mock_config():
    from internal_linking_tool.config import Config
    return Config(
        sf_cli_path="/fake/path/sf_cli",
        server_port=9999,
        page_fetch_concurrency=2,
        page_fetch_timeout_seconds=5,
        gsc_credentials_path="/tmp/test_creds.json",
        gsc_token_path="/tmp/test_token.json",
    )
