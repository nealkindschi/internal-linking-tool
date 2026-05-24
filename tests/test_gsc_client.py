"""Tests for GSC Client."""

import pytest
from unittest.mock import patch, MagicMock
from internal_linking_tool.gsc_client import (
    GscClient, GscQueryResult, fetch_queries_for_url, build_impression_weighted_keywords,
)

SAMPLE_RESPONSE = {
    "rows": [
        {"keys": ["renewable energy", "/target/"], "clicks": 450, "impressions": 4000, "ctr": 0.11, "position": 3.0},
        {"keys": ["sustainable power", "/target/"], "clicks": 200, "impressions": 3000, "ctr": 0.07, "position": 5.0},
        {"keys": ["green energy", "/target/"], "clicks": 100, "impressions": 2000, "ctr": 0.05, "position": 8.0},
        {"keys": ["clean power", "/target/"], "clicks": 50, "impressions": 1000, "ctr": 0.05, "position": 12.0},
    ],
}


class TestGscQueryResult:
    def test_from_api_row(self):
        row = {"keys": ["solar energy", "/page/"], "clicks": 100, "impressions": 500}
        result = GscQueryResult.from_api_row(row)
        assert result.query == "solar energy"
        assert result.clicks == 100
        assert result.impressions == 500

    def test_impression_share(self):
        r1 = GscQueryResult(query="a", page="/", clicks=10, impressions=500)
        r2 = GscQueryResult(query="b", page="/", clicks=10, impressions=300)
        r3 = GscQueryResult(query="c", page="/", clicks=10, impressions=200)
        total = 1000
        assert r1.impression_share(total) == 0.5
        assert r3.impression_share(total) == 0.2

    def test_impression_share_zero_total(self):
        r = GscQueryResult(query="a", page="/", clicks=0, impressions=0)
        assert r.impression_share(0) == 0.0


class TestFetchQueriesForUrl:
    @patch("internal_linking_tool.gsc_client.GscClient")
    def test_returns_parsed_results(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.query_search_analytics.return_value = SAMPLE_RESPONSE
        mock_client.is_authenticated = True
        mock_client_class.return_value = mock_client

        results = fetch_queries_for_url("https://example.com/target/", mock_client)
        assert len(results) == 4
        assert results[0].query == "renewable energy"

    @patch("internal_linking_tool.gsc_client.GscClient")
    def test_handles_empty_response(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.query_search_analytics.return_value = {}
        mock_client.is_authenticated = True
        mock_client_class.return_value = mock_client

        results = fetch_queries_for_url("https://example.com/target/", mock_client)
        assert results == []


class TestBuildImpressionWeightedKeywords:
    def test_distributes_by_impression_share(self):
        results = [
            GscQueryResult(query="renewable energy", page="/", impressions=4000),
            GscQueryResult(query="sustainable power", page="/", impressions=3000),
            GscQueryResult(query="green energy", page="/", impressions=2000),
            GscQueryResult(query="clean power", page="/", impressions=1000),
        ]
        keywords = build_impression_weighted_keywords(results)
        assert keywords[0]["keyword"] == "renewable energy"
        assert keywords[0]["impression_share"] == pytest.approx(0.4, rel=0.01)
        assert keywords[-1]["impression_share"] == pytest.approx(0.1, rel=0.01)

    def test_handles_empty_input(self):
        assert build_impression_weighted_keywords([]) == []

    def test_single_query_gets_100_percent(self):
        results = [GscQueryResult(query="only query", page="/", impressions=100)]
        keywords = build_impression_weighted_keywords(results)
        assert len(keywords) == 1
        assert keywords[0]["impression_share"] == 1.0
