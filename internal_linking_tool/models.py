"""Pydantic models for the Internal Linking Tool."""

from pydantic import BaseModel
from typing import Optional


class CrawlInfo(BaseModel):
    id: str
    name: str
    date: str
    url_count: int


class CrawlStatus(BaseModel):
    id: str
    phase: str
    percent: float = 0.0
    urls_crawled: int = 0


class AnalysisRequest(BaseModel):
    target_url: str
    crawl_id: Optional[str] = None


class AnalysisStatus(BaseModel):
    id: str
    phase: str
    percent: float = 0.0
    detail: str = ""


class Match(BaseModel):
    keyword: str
    anchor_text: str = ""
    variations: list[str] = []
    generation_method: str = "heuristic"
    impression_share: float
    context: str


class Opportunity(BaseModel):
    source_url: str
    link_authority: int
    organic_clicks_90d: int = 0
    match_count: int
    best_anchor: str
    matches: list[Match] = []


class AnalysisResults(BaseModel):
    opportunities: list[Opportunity]
    meta: dict


class HealthResponse(BaseModel):
    sf_installed: bool
    sf_path: str
    gsc_configured: bool
    server: str = "ok"
