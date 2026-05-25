"""Tests for Match Engine."""

import pytest
from internal_linking_tool.match_engine import (
    MatchEngine, keyword_in_text, is_linked, is_content_linked,
    score_opportunity, group_by_source_url,
)
from internal_linking_tool.csv_parser import CrawlPage
from internal_linking_tool.page_fetcher import FetchedPage


class TestKeywordInText:
    def test_finds_exact_match(self):
        assert keyword_in_text("renewable energy", "The future of renewable energy is bright.") is True

    def test_case_insensitive(self):
        assert keyword_in_text("Renewable Energy", "the future of RENEWABLE energy is bright.") is True

    def test_partial_word_not_matched(self):
        assert keyword_in_text("heat", "the heater is broken") is False

    def test_punctuation_boundary(self):
        assert keyword_in_text("renewable energy", "Focus on renewable energy.") is True

    def test_keyword_not_found(self):
        assert keyword_in_text("nuclear power", "renewable energy is key") is False

    def test_empty_text(self):
        assert keyword_in_text("anything", "") is False


class TestIsLinked:
    def test_detects_existing_link_relative(self):
        outlinks = ["/about/", "/blog/target-page/", "/contact/"]
        assert is_linked("/blog/target-page/", outlinks) is True

    def test_no_link_found(self):
        outlinks = ["/about/", "/contact/"]
        assert is_linked("/blog/target-page/", outlinks) is False

    def test_handles_trailing_slash_variation(self):
        outlinks = ["/blog/target-page/"]
        assert is_linked("/blog/target-page", outlinks) is True


class TestIsContentLinked:
    def test_excludes_when_found(self):
        content_dests = {"/about/", "/blog/target-page/", "/contact/"}
        assert is_content_linked("/blog/target-page/", content_dests) is True

    def test_allows_when_not_found(self):
        content_dests = {"/about/", "/contact/"}
        assert is_content_linked("/blog/target-page/", content_dests) is False

    def test_handles_trailing_slash_variation(self):
        content_dests = {"/blog/target-page/"}
        assert is_content_linked("/blog/target-page", content_dests) is True

    def test_handles_full_urls(self):
        content_dests = {"https://example.com/blog/target-page/"}
        assert is_content_linked("/blog/target-page/", content_dests) is True

    def test_empty_set_returns_false(self):
        assert is_content_linked("/target/", set()) is False


class TestScoreOpportunity:
    def test_higher_authority_produces_higher_score(self):
        s1 = score_opportunity(94, 100)
        s2 = score_opportunity(48, 100)
        assert s1 > s2

    def test_zero_clicks_handled(self):
        score = score_opportunity(50, 0)
        assert score == 50  # falls back to link authority when no click data


class TestGroupBySourceUrl:
    def test_groups_multiple_matches_per_url(self):
        matches = [
            {"source_url": "/blog/a/", "keyword": "solar", "impression_share": 0.5},
            {"source_url": "/blog/a/", "keyword": "renewable", "impression_share": 0.3},
            {"source_url": "/blog/b/", "keyword": "solar", "impression_share": 0.2},
        ]
        grouped = group_by_source_url(matches)
        assert len(grouped) == 2
        a = next(g for g in grouped if g["source_url"] == "/blog/a/")
        assert a["match_count"] == 2

    def test_empty_matches(self):
        assert group_by_source_url([]) == []


class TestMatchEngine:
    def test_find_opportunities_basic(self):
        pages = [
            CrawlPage("https://example.com/blog/solar/", 200, 94, 45, ["/about/"], 100),
            CrawlPage("https://example.com/blog/wind/", 200, 87, 32, ["/about/", "/blog/target-page/"], 50),
        ]
        fetched = {
            "https://example.com/blog/solar/": FetchedPage(
                "https://example.com/blog/solar/", 200,
                "The future of renewable energy solutions depends on solar technology."),
            "https://example.com/blog/wind/": FetchedPage(
                "https://example.com/blog/wind/", 200,
                "Wind power is a key part of sustainable energy."),
        }
        keywords = [
            {"keyword": "renewable energy", "impression_share": 0.6},
            {"keyword": "sustainable energy", "impression_share": 0.4},
        ]
        engine = MatchEngine(target_url="/blog/target-page/")
        results = engine.find_opportunities(pages, fetched, keywords)
        assert len(results) == 1
        assert results[0]["source_url"] == "https://example.com/blog/solar/"

    def test_excludes_pages_already_linking(self):
        pages = [
            CrawlPage("https://example.com/blog/a/", 200, 80, 10, ["/blog/target-page/"], 0),
        ]
        fetched = {
            "https://example.com/blog/a/": FetchedPage(
                "https://example.com/blog/a/", 200, "renewable energy is important."),
        }
        keywords = [{"keyword": "renewable energy", "impression_share": 1.0}]
        engine = MatchEngine(target_url="/blog/target-page/")
        results = engine.find_opportunities(pages, fetched, keywords)
        assert results == []

    def test_returns_empty_when_no_keywords(self):
        pages = [CrawlPage("/a/", 200, 50, 1, [], 0)]
        fetched = {"/a/": FetchedPage("/a/", 200, "hello world")}
        engine = MatchEngine(target_url="/target/")
        results = engine.find_opportunities(pages, fetched, [])
        assert results == []

    def test_find_opportunities_content_only_exclusion(self):
        pages = [
            CrawlPage("https://example.com/blog/nav-link/", 200, 80, 10, [], 0),
            CrawlPage("https://example.com/blog/content-link/", 200, 85, 20, [], 0),
        ]
        fetched = {
            "https://example.com/blog/nav-link/": FetchedPage(
                "https://example.com/blog/nav-link/", 200,
                "renewable energy is important for the future."),
            "https://example.com/blog/content-link/": FetchedPage(
                "https://example.com/blog/content-link/", 200,
                "sustainable energy powers our world."),
        }
        keywords = [
            {"keyword": "renewable energy", "impression_share": 0.6},
            {"keyword": "sustainable energy", "impression_share": 0.4},
        ]
        outlink_map = {
            "https://example.com/blog/nav-link/": {
                "all": {"/blog/target-page/"},
                "content": {},
                "content_dests": set(),
            },
            "https://example.com/blog/content-link/": {
                "all": {"/blog/target-page/"},
                "content": {"/blog/target-page/": "target page"},
                "content_dests": {"/blog/target-page/"},
            },
        }
        engine = MatchEngine(target_url="/blog/target-page/")
        results = engine.find_opportunities(pages, fetched, keywords, outlink_map)
        assert len(results) == 1
        assert results[0]["source_url"] == "https://example.com/blog/nav-link/"

    def test_find_opportunities_legacy_fallback(self):
        pages = [
            CrawlPage("https://example.com/blog/linked/", 200, 80, 10, [], 0),
            CrawlPage("https://example.com/blog/unlinked/", 200, 85, 20, [], 0),
        ]
        fetched = {
            "https://example.com/blog/linked/": FetchedPage(
                "https://example.com/blog/linked/", 200,
                "renewable energy is important."),
            "https://example.com/blog/unlinked/": FetchedPage(
                "https://example.com/blog/unlinked/", 200,
                "sustainable energy is growing."),
        }
        keywords = [
            {"keyword": "renewable energy", "impression_share": 0.6},
            {"keyword": "sustainable energy", "impression_share": 0.4},
        ]
        outlink_map = {
            "https://example.com/blog/linked/": {"/blog/target-page/"},
        }
        engine = MatchEngine(target_url="/blog/target-page/")
        results = engine.find_opportunities(pages, fetched, keywords, outlink_map)
        assert len(results) == 1
        assert results[0]["source_url"] == "https://example.com/blog/unlinked/"
