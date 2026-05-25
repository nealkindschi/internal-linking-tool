"""Analysis orchestrator: coordinates the full pipeline."""

import uuid
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from internal_linking_tool.csv_parser import parse_crawl_csv
from internal_linking_tool.gsc_client import GscClient, GscQueryResult, fetch_queries_for_url, build_impression_weighted_keywords
from internal_linking_tool.page_fetcher import PageFetcher, PageMetadata, extract_page_metadata
from internal_linking_tool.match_engine import MatchEngine
from internal_linking_tool.anchor_engine import AnchorEngine
from internal_linking_tool.llm_client import LlmAnchorClient
from internal_linking_tool.config import config
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
        self.anchor_engine = AnchorEngine(
            llm_client=self._init_llm_client(),
            max_variations=config.llm_max_variations,
        )

    def _init_llm_client(self):
        if not config.llm_enabled or not config.llm_api_key:
            return None
        return LlmAnchorClient(
            endpoint=config.llm_endpoint,
            api_key=config.llm_api_key,
            model=config.llm_model,
        )

    async def emit_progress(self, stream_id, state):
        await sse_emitter.emit(stream_id, "progress", state.to_dict())

    def fetch_gsc_data(self, target_url, site_url=None):
        return fetch_queries_for_url(target_url, self.gsc_client, site_url)

    def parse_crawl(self, csv_path):
        return parse_crawl_csv(csv_path)

    def parse_outlinks(self, outlinks_csv):
        if not outlinks_csv:
            return {}
        df = pd.read_csv(outlinks_csv, dtype=str, encoding="utf-8-sig")
        link_map = {}
        for _, row in df.iterrows():
            src = str(row.get("Source", "")).strip()
            dst = str(row.get("Destination", "")).strip()
            if src and dst:
                link_map.setdefault(src, set()).add(dst)
        return link_map

    async def fetch_source_pages(self, pages):
        urls = [p.url for p in pages if p.is_eligible]
        results = await self.page_fetcher.fetch_batch(urls)
        return {r.url: r for r in results}

    async def fetch_target_metadata(self):
        fetched = await self.page_fetcher.fetch(self.target_url)
        if fetched.success:
            return extract_page_metadata(fetched.raw_html, self.target_url)
        return PageMetadata()

    def match(self, pages, fetched_pages, queries, outlink_map=None):
        keywords = build_impression_weighted_keywords(queries)
        return self.match_engine.find_opportunities(pages, fetched_pages, keywords, outlink_map)

    def enrich(self, opportunities, queries, target_metadata=None):
        return self.anchor_engine.enrich_opportunities(opportunities, queries, target_metadata)

    async def run(self, csv_path, outlinks_csv=None, stream_id=None):
        state = AnalysisState(id=str(uuid.uuid4())[:8])

        state.set_phase("gsc_fetch", "Fetching Google Search Console data...", 10)
        if stream_id:
            await self.emit_progress(stream_id, state)
        try:
            queries = self.fetch_gsc_data(self.target_url)
        except Exception as e:
            queries = []
            state.detail = f"GSC fetch failed (continuing without): {e}"

        if not queries:
            try:
                target_page = await self.page_fetcher.fetch(self.target_url)
                if target_page.success:
                    keywords = _extract_keywords_from_text(target_page.text)
                    queries = [GscQueryResult(query=kw, page=self.target_url, impressions=1) for kw in keywords]
                    state.detail = f"GSC unavailable, using {len(queries)} on-page keywords instead"
            except Exception:
                pass

        state.set_phase("target_fetch", "Analyzing target page...", 20)
        if stream_id:
            await self.emit_progress(stream_id, state)
        target_metadata = await self.fetch_target_metadata()

        state.set_phase("csv_parse", "Parsing crawl data...", 30)
        if stream_id:
            await self.emit_progress(stream_id, state)
        pages = self.parse_crawl(csv_path)
        outlink_map = self.parse_outlinks(outlinks_csv)
        eligible = [p for p in pages if p.is_eligible]

        state.set_phase("page_scan", f"Scanning {len(eligible)} pages...", 40)
        if stream_id:
            await self.emit_progress(stream_id, state)
        fetched = await self.fetch_source_pages(pages)
        state.set_phase("page_scan", f"Scanned {len(fetched)} pages", 70)

        state.set_phase("matching", "Finding opportunities...", 80)
        if stream_id:
            await self.emit_progress(stream_id, state)
        opportunities = self.match(pages, fetched, queries, outlink_map)

        state.set_phase("matching", "Generating anchor suggestions...", 90)
        if stream_id:
            await self.emit_progress(stream_id, state)
        enriched = self.enrich(opportunities, queries, target_metadata)

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


def _extract_keywords_from_text(text):
    if not text:
        return []
    import re
    from collections import Counter
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    stopwords = {'this', 'that', 'with', 'from', 'they', 'will', 'have', 'been', 'were', 'their', 'about', 'which', 'there', 'would', 'could', 'should', 'these', 'those', 'because', 'through'}
    filtered = [w for w in words if w not in stopwords]
    bigrams = [' '.join(filtered[i:i+2]) for i in range(len(filtered)-1)]
    all_terms = filtered + bigrams
    counts = Counter(all_terms)
    top = [kw for kw, _ in counts.most_common(30)]
    return top[:20]


async def run_analysis(target_url, csv_path, outlinks_csv=None, stream_id=None):
    analyzer = Analyzer(target_url=target_url)
    return await analyzer.run(csv_path=csv_path, outlinks_csv=outlinks_csv, stream_id=stream_id)
