"""Tests for SF CLI Manager."""

import pytest
from unittest.mock import patch, MagicMock
from internal_linking_tool.sf_cli import SfCliManager, check_sf_installed


class TestCheckSfInstalled:
    @patch("internal_linking_tool.sf_cli.Path.exists")
    def test_returns_true_when_binary_exists(self, mock_exists):
        mock_exists.return_value = True
        assert check_sf_installed("/fake/sf") is True

    @patch("internal_linking_tool.sf_cli.Path.exists")
    def test_returns_false_when_binary_missing(self, mock_exists):
        mock_exists.return_value = False
        assert check_sf_installed("/fake/sf") is False


class TestSfCliManager:
    @patch("internal_linking_tool.sf_cli.subprocess.run")
    def test_list_crawls_parses_output(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = (
            "ID: abc123  Name: example.com  Date: 2026-05-20  URLs: 12440\n"
            "ID: def456  Name: example.com  Date: 2026-05-15  URLs: 11890\n")
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        manager = SfCliManager(cli_path="/fake/sf")
        crawls = manager.list_crawls()
        assert len(crawls) == 2
        assert crawls[0].id == "abc123"
        assert crawls[0].url_count == 12440

    @patch("internal_linking_tool.sf_cli.subprocess.run")
    def test_list_crawls_handles_empty_output(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "No saved crawls found."
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        manager = SfCliManager(cli_path="/fake/sf")
        crawls = manager.list_crawls()
        assert crawls == []

    @patch("internal_linking_tool.sf_cli.subprocess.run")
    def test_export_failure_raises(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: Database locked by GUI"
        mock_run.return_value = mock_result
        manager = SfCliManager(cli_path="/fake/sf")
        with pytest.raises(RuntimeError, match="GUI"):
            manager.export_crawl_data("abc123")
