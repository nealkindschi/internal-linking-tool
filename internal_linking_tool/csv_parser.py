"""Parse Screaming Frog internal_all.csv exports."""

import math
import pandas as pd
from dataclasses import dataclass, field


REQUIRED_COLUMNS = ["URL", "Status Code", "Link Score"]


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
        return self.status_code == 200 and self.link_authority > 0


def parse_outlinks(raw):
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    raw_str = str(raw).strip()
    if not raw_str:
        return []
    return [link.strip() for link in raw_str.split(",") if link.strip()]


def parse_crawl_csv(filepath):
    df = pd.read_csv(filepath, dtype=str)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

    pages = []
    for _, row in df.iterrows():
        try:
            status_code = int(float(row.get("Status Code", 0)))
            link_authority = int(float(row.get("Link Score", 0)))
        except (ValueError, TypeError):
            continue

        page = CrawlPage(
            url=str(row["URL"]),
            status_code=status_code,
            link_authority=link_authority,
            unique_inlinks=int(float(row.get("Unique Inlinks", 0))),
            outlinks=parse_outlinks(row.get("Outlinks", "")),
            gsc_clicks=_safe_int(row.get("GSC Clicks", 0)),
        )
        pages.append(page)

    return pages


def _safe_int(value):
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0
