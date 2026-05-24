"""Analysis orchestrator: coordinates the full pipeline."""

import uuid
from dataclasses import dataclass
from typing import Optional

from internal_linking_tool.csv_parser import parse_crawl_csv
from internal_linking_tool.gsc_client import GscClient, fetch_queries_for_url, build_impression_weighted_keywords
from internal_linking_tool.page_fetcher import PageFetcher
from internal_linking_tool.match_engine import MatchEngine
from internal_linking_tool.anchor_engine import AnchorEngine
from internal_linking_tool.sse import sse_emitter


@dataclass
class AnalysisState:
    id: str
    phase: str = "pending"
    percent: float = 0.0
    detail: str = ""

    def set_phase(self, phase, detail="", percent=0.0):
        self.phase = phase
        self.detail = detail
        self.percent = percent

    def to_dict(self):
        return {"id": self.id, "phase": self.phase, "percent": self.percent, "detail": self.detail}


class Analyzer:
    def __init__(self, target_url, gsc_client=None, page_fetcher=None):
        self.target_url = target_url
        self.gsc_client = gsc_client or GscClient()
        self.page_fetcher = page_fetcher or PageFetcher()
        self.match_engine = MatchEngine(target_url=target_url)
        self.anchor_engine = AnchorEngine()

    async def emit_progress(self, stream_id, state):
        await sse_emitter.emit(stream_id, "progress", state.to_dict())

    def fetch_gsc_data(self, target_url, site_url=None):
        return fetch_queries_for_url(target_url, self.gsc_client, site_url)

    def parse_crawl(self, csv_path):
        return parse_crawl_csv(csv_path)

    async def fetch_source_pages(self, pages):
        urls = [p.url for p in pages if p.is_eligible]
        results = await self.page_fetcher.fetch_batch(urls)
        return {r.url: r for r in results}

    def match(self, pages, fetched_pages, queries):
        keywords = build_impression_weighted_keywords(queries)
        return self.match_engine.find_opportunities(pages, fetched_pages, keywords)

    def enrich(self, opportunities, queries):
        return self.anchor_engine.enrich_opportunities(opportunities, queries)

    async def run(self, csv_path, stream_id=None):
        state = AnalysisState(id=str(uuid.uuid4())[:8])

        state.set_phase("gsc_fetch", "Fetching Google Search Console data...", 10)
        if stream_id:
            await self.emit_progress(stream_id, state)
        try:
            queries = self.fetch_gsc_data(self.target_url)
        except Exception as e:
            queries = []
            state.detail = f"GSC fetch failed (continuing without): {e}"

        state.set_phase("csv_parse", "Parsing crawl data...", 30)
        if stream_id:
            await self.emit_progress(stream_id, state)
        pages = self.parse_crawl(csv_path)
        eligible = [p for p in pages if p.is_eligible]

        state.set_phase("page_scan", f"Scanning {len(eligible)} pages...", 40)
        if stream_id:
            await self.emit_progress(stream_id, state)
        fetched = await self.fetch_source_pages(pages)
        state.set_phase("page_scan", f"Scanned {len(fetched)} pages", 70)

        state.set_phase("matching", "Finding opportunities...", 80)
        if stream_id:
            await self.emit_progress(stream_id, state)
        opportunities = self.match(pages, fetched, queries)

        state.set_phase("matching", "Generating anchor suggestions...", 90)
        if stream_id:
            await self.emit_progress(stream_id, state)
        enriched = self.enrich(opportunities, queries)

        state.set_phase("complete", f"Found {len(enriched)} opportunities", 100)
        if stream_id:
            await self.emit_progress(stream_id, state)

        return {
            "analysis_id": state.id,
            "results": enriched,
            "meta": {
                "total_opportunities": len(enriched),
                "total_anchor_options": sum(o.get("match_count", 0) for o in enriched),
                "pages_scanned": len(fetched),
                "gsc_keywords": len(queries),
                "page": 1,
                "per_page": 100,
            },
        }


async def run_analysis(target_url, csv_path, stream_id=None):
    analyzer = Analyzer(target_url=target_url)
    return await analyzer.run(csv_path=csv_path, stream_id=stream_id)
