"""Configuration for the Internal Linking Tool."""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Screaming Frog
    sf_cli_path: str = field(
        default_factory=lambda: os.getenv(
            "SF_CLI_PATH",
            "/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher",
        )
    )

    # GSC
    gsc_credentials_path: str = field(
        default_factory=lambda: os.getenv(
            "GSC_CREDENTIALS_PATH",
            str(Path.home() / ".config" / "internal-linking-tool" / "gsc_credentials.json"),
        )
    )
    gsc_token_path: str = field(
        default_factory=lambda: os.getenv(
            "GSC_TOKEN_PATH",
            str(Path.home() / ".config" / "internal-linking-tool" / "gsc_token.json"),
        )
    )
    gsc_scopes: list[str] = field(
        default_factory=lambda: ["https://www.googleapis.com/auth/webmasters.readonly"]
    )

    # Server
    server_host: str = "127.0.0.1"
    server_port: int = 8765

    # Page Fetcher
    page_fetch_concurrency: int = 10
    page_fetch_timeout_seconds: int = 30
    page_fetch_user_agent: str = "InternalLinkingTool/0.1"

    # Crawl
    crawl_timeout_seconds: int = 1800

    # Matching
    min_link_authority: int = 0

    # Cache
    gsc_cache_ttl_days: int = 7


# Singleton
config = Config()
