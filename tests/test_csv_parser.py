"""Tests for CSV Parser."""

import pytest
from internal_linking_tool.csv_parser import parse_crawl_csv, parse_outlinks, CrawlPage


class TestParseCrawlCsv:
    def test_parses_valid_csv(self, sample_crawl_csv):
        pages = parse_crawl_csv(sample_crawl_csv)
        assert len(pages) == 5

    def test_extracts_url_and_status(self, sample_crawl_csv):
        pages = parse_crawl_csv(sample_crawl_csv)
        solar = [p for p in pages if "solar-panel" in p.url][0]
        assert solar.url == "https://example.com/blog/solar-panel-guide-2024"
        assert solar.status_code == 200

    def test_extracts_link_authority(self, sample_crawl_csv):
        pages = parse_crawl_csv(sample_crawl_csv)
        solar = [p for p in pages if "solar-panel" in p.url][0]
        assert solar.link_authority == 94

    def test_filters_non_200_pages(self, sample_crawl_csv):
        pages = parse_crawl_csv(sample_crawl_csv)
        eligible = [p for p in pages if p.is_eligible]
        assert len(eligible) == 2  # 404, 301, and canonicalized (200/0) excluded
        for p in eligible:
            assert p.status_code == 200
            assert p.link_authority > 0

    def test_handles_empty_csv(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("Address,Status Code,Link Score\n")
        pages = parse_crawl_csv(str(csv_path))
        assert pages == []

    def test_missing_columns_raises_error(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("Address,Status\nhttps://example.com,200\n")
        with pytest.raises(ValueError, match="Missing required columns"):
            parse_crawl_csv(str(csv_path))


class TestParseOutlinks:
    def test_parses_comma_separated_outlinks(self):
        result = parse_outlinks("https://example.com/a/,https://example.com/b/")
        assert result == ["https://example.com/a/", "https://example.com/b/"]

    def test_handles_single_outlink(self):
        result = parse_outlinks("https://example.com/a/")
        assert result == ["https://example.com/a/"]

    def test_handles_empty_outlinks(self):
        assert parse_outlinks("") == []

    def test_handles_nan_outlinks(self):
        import math
        assert parse_outlinks(float("nan")) == []
        assert parse_outlinks(None) == []

    def test_trims_whitespace(self):
        result = parse_outlinks(" https://example.com/a/ , https://example.com/b/ ")
        assert result == ["https://example.com/a/", "https://example.com/b/"]
