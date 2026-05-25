"""Tests for Markdown CSV integration."""
import pytest
import tempfile
import csv
from pathlib import Path
from internal_linking_tool.match_engine import MatchEngine, _extract_context_markdown, _extract_context
from internal_linking_tool.csv_parser import CrawlPage
from internal_linking_tool.page_fetcher import FetchedPage


def _write_markdown_csv(rows):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    writer = csv.writer(tmp)
    writer.writerow(["Address", "Content Type", "Status Code", "Status", "Page Markdown 1"])
    for row in rows:
        writer.writerow(row)
    tmp.close()
    return tmp.name


SAMPLE_MD_TEXT = """---
title: Solar Power Guide
author: John Doe
---

Solar energy is a renewable energy source that converts sunlight into electricity.

This paragraph mentions renewable energy and solar panels.

Another section about sustainable energy for the future.
"""


class TestExtractContextMarkdown:
    def test_returns_paragraph_containing_keyword(self):
        result = _extract_context_markdown("renewable energy", SAMPLE_MD_TEXT)
        assert "renewable energy" in result
        assert "Solar energy is a" in result
        assert len(result) <= 500

    def test_falls_back_to_window_on_no_paragraph_match(self):
        text = "just a single line without proper paragraph breaks"
        result = _extract_context_markdown("single line", text)
        assert "single line" in result

    def test_handles_empty_text(self):
        assert _extract_context_markdown("anything", "") == ""

    def test_respects_500_char_cap(self):
        long_md = "\n\n".join(["paragraph " + str(i) * 100 for i in range(20)])
        result = _extract_context_markdown("10", long_md)
        assert len(result) <= 500


class TestMatchEngineWithMarkdown:
    def test_prefers_markdown_over_fetched_text(self):
        pages = [
            CrawlPage("https://example.com/blog/solar/", 200, 94, 45, [], 0),
        ]
        md_map = {
            "https://example.com/blog/solar/": SAMPLE_MD_TEXT,
        }
        fetched = {
            "https://example.com/blog/solar/": FetchedPage(
                "https://example.com/blog/solar/", 200, "different text that does not match"),
        }
        keywords = [{"keyword": "renewable energy", "impression_share": 1.0}]
        engine = MatchEngine(target_url="/blog/target/")
        results = engine.find_opportunities(pages, fetched, keywords, markdown_map=md_map)
        assert len(results) == 1
        assert "renewable energy" in results[0]["matches"][0]["context"]

    def test_falls_back_to_fetched_when_no_markdown(self):
        pages = [
            CrawlPage("https://example.com/blog/solar/", 200, 94, 45, [], 0),
        ]
        fetched = {
            "https://example.com/blog/solar/": FetchedPage(
                "https://example.com/blog/solar/", 200, "Solar power is a renewable energy source."),
        }
        keywords = [{"keyword": "renewable energy", "impression_share": 1.0}]
        engine = MatchEngine(target_url="/blog/target/")
        results = engine.find_opportunities(pages, fetched, keywords)
        assert len(results) == 1

    def test_extracts_paragraph_context_from_markdown(self):
        pages = [
            CrawlPage("https://example.com/blog/solar/", 200, 94, 45, [], 0),
        ]
        md_map = {
            "https://example.com/blog/solar/": SAMPLE_MD_TEXT,
        }
        fetched = {
            "https://example.com/blog/solar/": FetchedPage(
                "https://example.com/blog/solar/", 200, ""),
        }
        keywords = [{"keyword": "renewable energy", "impression_share": 1.0}]
        engine = MatchEngine(target_url="/blog/target/")
        results = engine.find_opportunities(pages, fetched, keywords, markdown_map=md_map)
        ctx = results[0]["matches"][0]["context"]
        assert len(ctx) < 500
        assert "renewable energy" in ctx


class TestParseMarkdownCsv:
    def test_parse_markdown_csv(self):
        from internal_linking_tool.analyzer import Analyzer
        analyzer = Analyzer(target_url="https://example.com/target/")
        path = _write_markdown_csv([
            ["https://example.com/a/", "text/html", "200", "OK", "# Heading\n\nSome content."],
        ])
        try:
            result = analyzer.parse_markdown_csv(path)
            assert "https://example.com/a/" in result
            assert "# Heading" in result["https://example.com/a/"]
        finally:
            Path(path).unlink(missing_ok=True)

    def test_parse_markdown_csv_no_file_returns_empty(self):
        from internal_linking_tool.analyzer import Analyzer
        analyzer = Analyzer(target_url="https://example.com/target/")
        assert analyzer.parse_markdown_csv(None) == {}
        assert analyzer.parse_markdown_csv("") == {}
