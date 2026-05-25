"""Parse Screaming Frog internal_all.csv exports."""

import math
import re
import pandas as pd
from dataclasses import dataclass, field


_NON_PAGE_EXTENSIONS = re.compile(r'\.(js|css|xml|json|png|jpg|jpeg|gif|svg|webp|ico|pdf|zip|gz|woff2?|ttf|eot|mp4|webm)(\?|$)', re.IGNORECASE)
_NON_PAGE_PATHS = ['cdn-cgi/', 'wp-content/plugins/', 'wp-includes/', 'wp-json/', 'feed/', 'xmlrpc.php']


def _safe_str(value):
    if pd.isna(value):
        return "0"
    return str(value).strip() or "0"


REQUIRED_COLUMNS = ["Address", "Status Code", "Link Score"]


@dataclass
class CrawlPage:
    url: str
    status_code: int
    link_authority: int
    unique_inlinks: int
    outlinks: list[str] = field(default_factory=list)
    gsc_clicks: int = 0

    @property
    def is_eligible(self) -> bool:
        if self.status_code != 200:
            return False
        if _NON_PAGE_EXTENSIONS.search(self.url):
            return False
        for path in _NON_PAGE_PATHS:
            if path in self.url:
                return False
        return True


def parse_outlinks(raw):
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    raw_str = str(raw).strip()
    if not raw_str:
        return []
    return [link.strip() for link in raw_str.split(",") if link.strip()]


def parse_crawl_csv(filepath):
    df = pd.read_csv(filepath, dtype=str, encoding="utf-8-sig")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

    pages = []
    for _, row in df.iterrows():
        try:
            status_code = int(float(_safe_str(row.get("Status Code", "0"))))
            link_authority = int(float(_safe_str(row.get("Link Score", "0"))))
        except (ValueError, TypeError):
            continue

        page = CrawlPage(
            url=str(row["Address"]),
            status_code=status_code,
            link_authority=link_authority,
            unique_inlinks=_safe_int(row.get("Unique Inlinks", 0)),
            outlinks=parse_outlinks(row.get("Outlinks", "")),
            gsc_clicks=_safe_int(row.get("GSC Clicks", 0)),
        )
        pages.append(page)

    return pages


def _safe_int(value):
    try:
        if pd.isna(value):
            return 0
        return int(float(value))
    except (ValueError, TypeError):
        return 0
