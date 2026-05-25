"""Tests for Anchor Text Engine."""

import pytest
from internal_linking_tool.anchor_engine import (
    AnchorEngine, distribute_anchors, _trim_title, _clean_keyword,
)
from internal_linking_tool.gsc_client import GscQueryResult
from internal_linking_tool.page_fetcher import PageMetadata


SAMPLE_QUERIES = [
    GscQueryResult(query="renewable energy solutions", page="/target/", impressions=4000),
    GscQueryResult(query="renewable energy", page="/target/", impressions=2500),
    GscQueryResult(query="sustainable power", page="/target/", impressions=2000),
    GscQueryResult(query="green energy options", page="/target/", impressions=1000),
    GscQueryResult(query="clean power sources", page="/target/", impressions=500),
]

SAMPLE_METADATA = PageMetadata(
    title="Renewable Energy Guide | Example Site",
    h1="Complete Guide to Renewable Energy",
    slug="renewable energy guide",
    description="A comprehensive guide to renewable energy sources and solutions.",
)


class TestTrimTitle:
    def test_removes_site_name_after_pipe(self):
        assert _trim_title("Renewable Energy Guide | Example Site") == "Renewable Energy Guide"

    def test_removes_site_name_after_dash(self):
        assert _trim_title("Renewable Energy Guide - Example Site") == "Renewable Energy Guide"

    def test_short_title_unchanged(self):
        assert _trim_title("Solar Power") == "Solar Power"

    def test_truncates_very_long_title(self):
        long_title = "A " * 50 + "Very Long Title That Exceeds Sixty Characters Limit"
        result = _trim_title(long_title)
        assert len(result) <= 60


class TestCleanKeyword:
    def test_removes_year(self):
        assert _clean_keyword("best laptops 2024") == "best laptops"

    def test_removes_how_to(self):
        result = _clean_keyword("how to fix pc fan")
        assert "how" not in result
        assert "fix pc fan" in result

    def test_removes_what_is(self):
        result = _clean_keyword("what is renewable energy")
        assert "what" not in result
        assert "renewable energy" in result

    def test_strips_question_mark(self):
        assert _clean_keyword("best solar panels?") == "best solar panels"

    def test_preserves_clean_keywords(self):
        assert _clean_keyword("solar panel installation") == "solar panel installation"

    def test_handles_empty_string(self):
        assert _clean_keyword("") == ""

    def test_deduplicates_spaces(self):
        assert _clean_keyword("how  to  fix") == "fix"


class TestAnchorEngineHeuristic:
    def test_uses_title_as_primary(self):
        engine = AnchorEngine()
        anchor, variations, method = engine._generate_via_heuristic(
            SAMPLE_METADATA, "renewable energy solutions"
        )
        assert method == "heuristic"
        assert anchor == "Renewable Energy Guide"
        assert len(variations) >= 1

    def test_falls_to_h1_when_no_title(self):
        engine = AnchorEngine()
        meta = PageMetadata(title="", h1="Renewable Energy Overview", slug="renewable-energy")
        anchor, variations, method = engine._generate_via_heuristic(meta, "renewable energy")
        assert method == "heuristic"
        assert "Renewable Energy Overview" in anchor

    def test_falls_to_slug_when_no_title_or_h1(self):
        engine = AnchorEngine()
        meta = PageMetadata(title="", h1="", slug="renewable energy guide")
        anchor, variations, method = engine._generate_via_heuristic(meta, "renewable energy")
        assert method == "heuristic"
        assert anchor == "renewable energy guide"

    def test_falls_to_cleaned_keyword_as_last_resort(self):
        engine = AnchorEngine()
        meta = PageMetadata(title="", h1="", slug="")
        anchor, variations, method = engine._generate_via_heuristic(
            meta, "how to fix pc fan 2024"
        )
        assert method == "heuristic"
        assert len(anchor) > 0
        assert "how" not in anchor.lower()

    def test_does_not_duplicate_primary_in_variations(self):
        engine = AnchorEngine()
        meta = PageMetadata(
            title="Solar Power Guide",
            h1="Solar Power Guide",
            slug="solar power guide",
        )
        anchor, variations, method = engine._generate_via_heuristic(meta, "solar power")
        assert method == "heuristic"
        assert anchor.lower() not in [v.lower() for v in variations]

    def test_variations_deduplicated(self):
        engine = AnchorEngine()
        meta = PageMetadata(title="Hello", h1="Hello", slug="hello")
        anchor, variations, _ = engine._generate_via_heuristic(meta, "hello")
        assert len(variations) <= 2


class TestEnrichOpportunities:
    def test_sets_anchor_text_and_variations(self):
        engine = AnchorEngine()
        opportunities = [
            {
                "source_url": "/a/",
                "link_authority": 94,
                "matches": [
                    {"keyword": "renewable energy solutions", "impression_share": 0.4, "context": "The future of renewable energy solutions is bright."},
                ],
            },
        ]
        result = engine.enrich_opportunities(opportunities, SAMPLE_QUERIES, SAMPLE_METADATA)
        assert len(result) == 1
        match = result[0]["matches"][0]
        assert match.get("anchor_text")
        assert isinstance(match.get("variations"), list)
        assert match.get("generation_method") == "heuristic"

    def test_sets_best_anchor_from_first_match(self):
        engine = AnchorEngine()
        opportunities = [
            {
                "source_url": "/a/",
                "link_authority": 94,
                "matches": [
                    {"keyword": "renewable energy", "impression_share": 0.5, "context": "ctx"},
                    {"keyword": "solar power", "impression_share": 0.3, "context": "ctx"},
                ],
            },
        ]
        result = engine.enrich_opportunities(opportunities, SAMPLE_QUERIES, SAMPLE_METADATA)
        assert result[0].get("best_anchor")

    def test_handles_empty_metadata(self):
        engine = AnchorEngine()
        opportunities = [
            {
                "source_url": "/a/",
                "link_authority": 50,
                "matches": [
                    {"keyword": "how to test anchor", "impression_share": 1.0, "context": "test"},
                ],
            },
        ]
        result = engine.enrich_opportunities(opportunities, [], PageMetadata())
        match = result[0]["matches"][0]
        assert match["anchor_text"]
        assert match["generation_method"] == "heuristic"

    def test_handles_empty_opportunities(self):
        engine = AnchorEngine()
        assert engine.enrich_opportunities([], [], SAMPLE_METADATA) == []


class TestBuildAnchorList:
    def test_builds_impression_weighted_list(self):
        engine = AnchorEngine()
        suggestions = engine.build_anchor_list(SAMPLE_QUERIES)
        assert len(suggestions) == 5
        assert suggestions[0]["keyword"] == "renewable energy solutions"
        assert suggestions[0]["impression_share"] == pytest.approx(0.4, rel=0.01)

    def test_handles_empty_queries(self):
        engine = AnchorEngine()
        assert engine.build_anchor_list([]) == []


class TestDistributeAnchors:
    def test_distributes_by_impression_share(self):
        opportunities = [
            {"source_url": f"/page/{i}/", "link_authority": 80, "matches": [{"keyword": f"kw{i}"}]}
            for i in range(10)
        ]
        keywords = [
            {"keyword": "primary kw", "impression_share": 0.40},
            {"keyword": "secondary kw", "impression_share": 0.30},
            {"keyword": "tertiary kw", "impression_share": 0.20},
            {"keyword": "long tail kw", "impression_share": 0.10},
        ]
        distributed = distribute_anchors(opportunities, keywords)
        primary_count = sum(1 for o in distributed if o["matches"][0]["keyword"] == "primary kw")
        assert primary_count == 4

    def test_handles_empty(self):
        assert distribute_anchors([], []) == []
