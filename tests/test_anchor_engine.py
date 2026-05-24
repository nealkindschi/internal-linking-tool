"""Tests for Anchor Text Engine."""

import pytest
from internal_linking_tool.anchor_engine import AnchorEngine, distribute_anchors
from internal_linking_tool.gsc_client import GscQueryResult


SAMPLE_QUERIES = [
    GscQueryResult(query="renewable energy solutions", page="/target/", impressions=4000),
    GscQueryResult(query="renewable energy", page="/target/", impressions=2500),
    GscQueryResult(query="sustainable power", page="/target/", impressions=2000),
    GscQueryResult(query="green energy options", page="/target/", impressions=1000),
    GscQueryResult(query="clean power sources", page="/target/", impressions=500),
]


class TestAnchorEngine:
    def test_builds_impression_weighted_list(self):
        engine = AnchorEngine()
        suggestions = engine.build_anchor_list(SAMPLE_QUERIES)
        assert len(suggestions) == 5
        assert suggestions[0]["keyword"] == "renewable energy solutions"
        assert suggestions[0]["impression_share"] == pytest.approx(0.4, rel=0.01)

    def test_handles_empty_queries(self):
        engine = AnchorEngine()
        assert engine.build_anchor_list([]) == []

    def test_suggests_variations_for_keyword(self):
        engine = AnchorEngine()
        variations = engine.get_variations("renewable energy solutions")
        assert "renewable energy" in variations or len(variations) > 1

    def test_generates_suggestions_for_opportunities(self):
        engine = AnchorEngine()
        opportunities = [
            {"source_url": "/a/", "link_authority": 94, "matches": [
                {"keyword": "renewable energy solutions", "impression_share": 0.4},
                {"keyword": "renewable energy", "impression_share": 0.25},
            ]},
            {"source_url": "/b/", "link_authority": 80, "matches": [
                {"keyword": "sustainable power", "impression_share": 0.2},
            ]},
        ]
        result = engine.enrich_opportunities(opportunities, SAMPLE_QUERIES)
        assert len(result) == 2


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
