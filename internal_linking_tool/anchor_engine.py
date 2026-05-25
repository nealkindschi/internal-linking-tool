"""Anchor Text Engine: LLM-powered + heuristic fallback anchor text generation."""

import re
import math
from typing import Optional

from internal_linking_tool.gsc_client import build_impression_weighted_keywords
from internal_linking_tool.page_fetcher import PageMetadata


class AnchorEngine:
    def __init__(self, llm_client=None, max_variations: int = 3):
        self.llm_client = llm_client
        self.max_variations = max_variations

    def build_anchor_list(self, queries):
        return build_impression_weighted_keywords(queries)

    def generate_anchors(
        self,
        target_metadata: PageMetadata,
        keyword: str,
        source_context: str,
    ) -> tuple[str, list[str], str]:
        primary, variations, method = self._try_llm(target_metadata, keyword, source_context)
        if primary:
            return (primary, variations, method)
        return self._generate_via_heuristic(target_metadata, keyword)

    def _try_llm(self, target_metadata, keyword, source_context):
        if not self.llm_client or not self.llm_client.is_available():
            return ("", [], "")
        target_dict = {
            "title": target_metadata.title,
            "h1": target_metadata.h1,
            "slug": target_metadata.slug,
            "description": target_metadata.description,
        }
        anchors = self.llm_client.generate_anchors(
            target_context=target_dict,
            keyword=keyword,
            source_context=source_context,
            max_variations=self.max_variations,
        )
        if not anchors or len(anchors) == 0:
            return ("", [], "")
        primary = anchors[0]
        variations = anchors[1:self.max_variations]
        return (primary, variations, "llm")

    def _generate_via_heuristic(self, target_metadata, keyword):
        title = target_metadata.title.strip() if target_metadata.title else ""
        h1 = target_metadata.h1.strip() if target_metadata.h1 else ""
        slug = target_metadata.slug.strip() if target_metadata.slug else ""

        if title:
            primary = _trim_title(title)
            variations = []
            if h1 and h1.lower() != primary.lower():
                variations.append(h1[:60].strip())
            if slug and slug.lower() != primary.lower():
                variations.append(slug[:60].strip())
            if len(variations) < 2:
                cleaned_kw = _clean_keyword(keyword)
                if cleaned_kw and cleaned_kw.lower() != primary.lower():
                    variations.append(cleaned_kw)
            return (primary, variations[:2], "heuristic")

        if h1:
            primary = h1[:60].strip()
            variations = []
            if slug and slug.lower() != primary.lower():
                variations.append(slug[:60].strip())
            cleaned_kw = _clean_keyword(keyword)
            if cleaned_kw and cleaned_kw.lower() != primary.lower():
                variations.append(cleaned_kw)
            return (primary, variations[:2], "heuristic")

        if slug:
            primary = slug[:60].strip()
            cleaned_kw = _clean_keyword(keyword)
            variations = [cleaned_kw] if cleaned_kw and cleaned_kw.lower() != primary.lower() else []
            return (primary, variations[:2], "heuristic")

        cleaned_kw = _clean_keyword(keyword)
        primary = cleaned_kw if cleaned_kw else keyword[:60].strip()
        if not primary or len(primary.split()) < 2:
            words = primary.split()
            if not words or words[0].lower() in _EXTENDED_STOPWORDS or len(words[0]) <= 3:
                primary = slug if slug else "related content"
        return (primary, [], "heuristic")

    def enrich_opportunities(self, opportunities, queries, target_metadata=None):
        if target_metadata is None:
            target_metadata = PageMetadata()
        if not opportunities:
            return opportunities
        for opp in opportunities:
            for match in opp.get("matches", []):
                kw = match.get("keyword", "")
                ctx = match.get("context", "")
                anchor, variations, method = self.generate_anchors(
                    target_metadata, kw, ctx
                )
                match["anchor_text"] = anchor
                match["variations"] = variations
                match["generation_method"] = method
            if opp.get("matches"):
                opp["best_anchor"] = opp["matches"][0].get("anchor_text", "")
        return opportunities

    def get_variations(self, keyword):
        words = keyword.lower().split()
        variations = [keyword]
        if len(words) > 1:
            variations.append(" ".join(words[:-1]))
        if len(words) > 1:
            variations.append(" ".join(words[1:]))
        if keyword.endswith("s") and not keyword.endswith("ss"):
            variations.append(keyword[:-1])
        seen = set()
        result = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result


def _trim_title(title: str) -> str:
    title = re.sub(r"\s*[|\-–—]\s*.+$", "", title).strip()
    if len(title) > 60:
        words = title.split()
        result = []
        char_count = 0
        for w in words:
            if char_count + len(w) > 60:
                break
            result.append(w)
            char_count += len(w) + 1
        title = " ".join(result)
    return title


_EXTENDED_STOPWORDS = {
    'your', 'what', 'when', 'where', 'across', 'every', 'into', 'more',
    'some', 'than', 'them', 'then', 'only', 'also', 'over', 'just', 'most',
    'other', 'after', 'before', 'between', 'during', 'without', 'within',
    'such', 'each', 'like', 'make', 'made', 'still', 'well', 'back', 'much',
    'even', 'part', 'same', 'does', 'many', 'being', 'while', 'under', 'around',
    'again', 'very', 'here', 'both', 'this', 'that', 'with', 'from', 'they',
    'will', 'have', 'been', 'were', 'their', 'about', 'which', 'there', 'would',
    'could', 'should', 'these', 'those', 'because', 'through',
}


def _clean_keyword(keyword: str) -> str:
    if not keyword:
        return ""
    kw = keyword.lower().strip()
    kw = re.sub(r"\b\d{4}\b", "", kw)
    question_words = [
        r"\bhow\s+to\b", r"\bwhat\s+is\b", r"\bwhat\s+are\b",
        r"\bwhy\s+do\b", r"\bwhy\s+is\b", r"\bwhy\s+are\b",
        r"\bcan\s+you\b", r"\bcan\s+i\b", r"\bwhere\s+to\b",
        r"\bwhen\s+to\b", r"\bwho\s+is\b", r"\bis\s+there\b",
    ]
    for pattern in question_words:
        kw = re.sub(pattern, "", kw)
    kw = re.sub(r"\?", "", kw)
    kw = re.sub(r"\s+", " ", kw).strip()
    if len(kw.split()) == 1 and kw in _EXTENDED_STOPWORDS:
        return ""
    return kw


def distribute_anchors(opportunities, keywords):
    if not keywords or not opportunities:
        return opportunities
    total_opps = len(opportunities)
    result = []
    targets = {}
    cumulative = 0
    for kw in keywords:
        count = math.ceil(total_opps * kw["impression_share"])
        targets[kw["keyword"]] = min(count, total_opps - cumulative)
        cumulative += targets[kw["keyword"]]
    opp_index = 0
    for kw_keyword, target_count in targets.items():
        for _ in range(target_count):
            if opp_index < len(opportunities):
                opp = dict(opportunities[opp_index])
                for match in opp.get("matches", []):
                    match["keyword"] = kw_keyword
                result.append(opp)
                opp_index += 1
    while opp_index < len(opportunities):
        result.append(dict(opportunities[opp_index]))
        opp_index += 1
    return result
