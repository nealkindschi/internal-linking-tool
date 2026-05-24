"""Google Search Console API client for query data extraction."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from internal_linking_tool.config import config


@dataclass
class GscQueryResult:
    query: str
    page: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0

    def impression_share(self, total_impressions: int) -> float:
        if total_impressions <= 0:
            return 0.0
        return self.impressions / total_impressions

    @classmethod
    def from_api_row(cls, row: dict) -> "GscQueryResult":
        keys = row.get("keys", [])
        return cls(
            query=keys[0] if len(keys) > 0 else "",
            page=keys[1] if len(keys) > 1 else "",
            clicks=row.get("clicks", 0),
            impressions=row.get("impressions", 0),
            ctr=row.get("ctr", 0.0),
            position=row.get("position", 0.0),
        )


class GscClient:
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        scopes: Optional[list[str]] = None,
    ):
        self.credentials_path = credentials_path or config.gsc_credentials_path
        self.token_path = token_path or config.gsc_token_path
        self.scopes = scopes or config.gsc_scopes
        self._credentials: Optional[Credentials] = None
        self._service = None

    def authenticate(self) -> bool:
        self._credentials = None
        token_file = Path(self.token_path)
        if token_file.exists():
            self._credentials = Credentials.from_authorized_user_file(
                str(token_file), self.scopes
            )
        if not self._credentials or not self._credentials.valid:
            if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                self._credentials.refresh(Request())
            else:
                creds_file = Path(self.credentials_path)
                if not creds_file.exists():
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_file), self.scopes
                )
                self._credentials = flow.run_local_server(port=0)
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(self._credentials.to_json())
        self._service = build("searchconsole", "v1", credentials=self._credentials)
        return True

    @property
    def is_authenticated(self) -> bool:
        return self._credentials is not None and self._credentials.valid

    def query_search_analytics(
        self,
        site_url: str,
        page_url: str,
        start_date: str = "2026-02-23",
        end_date: str = "2026-05-23",
        row_limit: int = 25000,
        dimensions: Optional[list[str]] = None,
    ) -> dict:
        if not self._service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        if dimensions is None:
            dimensions = ["query", "page"]
        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "dimensionFilterGroups": [{
                "filters": [{
                    "dimension": "page",
                    "operator": "equals",
                    "expression": page_url,
                }]
            }],
            "rowLimit": min(row_limit, 25000),
            "startRow": 0,
        }
        try:
            return self._service.searchanalytics().query(
                siteUrl=site_url, body=request_body
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"GSC API error: {e}") from e


def fetch_queries_for_url(
    target_url: str,
    client: Optional[GscClient] = None,
    site_url: Optional[str] = None,
) -> list[GscQueryResult]:
    if client is None:
        client = GscClient()
    if not client.is_authenticated:
        client.authenticate()
    from urllib.parse import urlparse
    if site_url is None:
        parsed = urlparse(target_url)
        site_url = f"{parsed.scheme}://{parsed.netloc}/"
    response = client.query_search_analytics(site_url=site_url, page_url=target_url)
    rows = response.get("rows", [])
    return [GscQueryResult.from_api_row(r) for r in rows]


def build_impression_weighted_keywords(results: list[GscQueryResult]) -> list[dict]:
    if not results:
        return []
    total_impressions = sum(r.impressions for r in results)
    if total_impressions == 0:
        return []
    keywords = []
    for r in sorted(results, key=lambda x: x.impressions, reverse=True):
        keywords.append({
            "keyword": r.query,
            "impressions": r.impressions,
            "impression_share": r.impression_share(total_impressions),
        })
    return keywords
