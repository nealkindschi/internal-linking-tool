"""Match Engine: find unlinked keyword mentions across crawled pages."""

import re
import math
from collections import defaultdict
from urllib.parse import urlparse

from internal_linking_tool.csv_parser import CrawlPage
from internal_linking_tool.page_fetcher import FetchedPage


def keyword_in_text(keyword, text):
    if not keyword or not text:
        return False
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))


def is_linked(target_url_path, outlinks):
    target_normalized = _normalize_path(target_url_path)
    for link in outlinks:
        parsed = urlparse(link)
        path_to_check = parsed.path if parsed.netloc else link
        if _normalize_path(path_to_check) == target_normalized:
            return True
    return False


def _normalize_path(path):
    path = path.strip().rstrip("/").lower()
    return path or "/"


def score_opportunity(link_authority, organic_clicks):
    return link_authority * math.log(organic_clicks + 1)


def group_by_source_url(matches):
    groups = defaultdict(list)
    for match in matches:
        groups[match["source_url"]].append(match)
    result = []
    for source_url, url_matches in groups.items():
        sorted_matches = sorted(url_matches, key=lambda m: m.get("impression_share", 0), reverse=True)
        result.append({
            "source_url": source_url,
            "link_authority": url_matches[0].get("link_authority", 0),
            "organic_clicks_90d": url_matches[0].get("organic_clicks_90d", 0),
            "match_count": len(sorted_matches),
            "best_anchor": sorted_matches[0].get("anchor_text", sorted_matches[0].get("keyword", "")),
            "matches": sorted_matches,
        })
    result.sort(key=lambda x: score_opportunity(x["link_authority"], x.get("organic_clicks_90d", 0)), reverse=True)
    return result


class MatchEngine:
    def __init__(self, target_url):
        self.target_url = target_url
        self.target_path = _normalize_path(urlparse(target_url).path)

    def find_opportunities(self, pages, fetched_pages, keywords):
        if not keywords:
            return []
        matches = []
        for page in pages:
            if not page.is_eligible:
                continue
            if is_linked(self.target_path, page.outlinks):
                continue
            fetched = fetched_pages.get(page.url)
            if not fetched or not fetched.success:
                continue
            page_text = fetched.text
            if not page_text:
                continue
            for kw in keywords:
                kw_text = kw["keyword"]
                if keyword_in_text(kw_text, page_text):
                    context = _extract_context(kw_text, page_text)
                    matches.append({
                        "source_url": page.url,
                        "link_authority": page.link_authority,
                        "organic_clicks_90d": page.gsc_clicks,
                        "keyword": kw_text,
                        "anchor_text": kw_text,
                        "impression_share": kw.get("impression_share", 0),
                        "context": context,
                    })
        return group_by_source_url(matches)


def _extract_context(keyword, text, window=80):
    pattern = r"\b" + re.escape(keyword) + r"\b"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    context = text[start:end].strip()
    if start > 0:
        context = "..." + context
    if end < len(text):
        context = context + "..."
    return context
