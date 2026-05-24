"""Screaming Frog CLI integration manager."""

import re
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass

from internal_linking_tool.config import config
from internal_linking_tool.models import CrawlStatus


@dataclass
class CrawlInfo:
    id: str
    name: str
    date: str
    url_count: int


def check_sf_installed(cli_path=None):  # type: (str|None) -> bool
    path = cli_path or config.sf_cli_path
    return Path(path).exists()


class SfCliManager:
    def __init__(self, cli_path=None):  # type: (str|None) -> None
        self.cli_path = cli_path or config.sf_cli_path

    def _run(self, args: list[str], timeout: int = 300):
        try:
            return subprocess.run(
                [self.cli_path] + args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"SF CLI command timed out after {timeout}s")
        except FileNotFoundError:
            raise RuntimeError(
                f"Screaming Frog CLI not found at '{self.cli_path}'. "
                "Install Screaming Frog or set SF_CLI_PATH.")

    def list_crawls(self) -> list[CrawlInfo]:
        result = self._run(["--list-crawls"])
        if "No saved crawls" in result.stdout or not result.stdout.strip():
            return []
        crawls = []
        pattern = re.compile(
            r"ID:\s*(?P<id>\S+)\s+Name:\s*(?P<name>.+?)\s+Date:\s*(?P<date>\S+)\s+URLs?:\s*(?P<urls>\d+)")
        for line in result.stdout.strip().split("\n"):
            match = pattern.search(line)
            if match:
                crawls.append(CrawlInfo(
                    id=match.group("id"), name=match.group("name").strip(),
                    date=match.group("date"), url_count=int(match.group("urls"))))
        return crawls

    def start_crawl(self, url: str) -> str:
        result = self._run(["--crawl", url, "--headless"], timeout=config.crawl_timeout_seconds)
        match = re.search(r"crawl[_\s]?id[:\s]*(\S+)", result.stdout, re.IGNORECASE)
        return match.group(1) if match else "unknown"

    def crawl_status(self, crawl_id: str) -> CrawlStatus:
        result = self._run(["--status", crawl_id])
        percent = 0.0
        urls = 0
        phase = "running"
        pct_match = re.search(r"(\d+)%", result.stdout)
        if pct_match:
            percent = float(pct_match.group(1))
        url_match = re.search(r"(\d+)\s*URLs?\s*crawled", result.stdout)
        if url_match:
            urls = int(url_match.group(1))
        if "complete" in result.stdout.lower() or percent >= 100:
            phase = "completed"
        elif "error" in result.stdout.lower() or "fail" in result.stdout.lower():
            phase = "failed"
        return CrawlStatus(id=crawl_id, phase=phase, percent=percent, urls_crawled=urls)

    def export_crawl_data(self, crawl_id, export_dir=None):  # type: (str, str|None) -> str
        if export_dir is None:
            export_dir = tempfile.mkdtemp(prefix="sf_export_")
        result = self._run(
            ["--export", f"--crawl-id={crawl_id}", f"--output-dir={export_dir}",
             "--export-tabs=Internal:All"], timeout=600)
        if result.returncode != 0:
            stderr = result.stderr.lower()
            if "gui" in stderr or "locked" in stderr or "database" in stderr:
                raise RuntimeError(
                    "Cannot access crawl data. The Screaming Frog GUI may be running. "
                    "Please close the Screaming Frog application and try again.")
            raise RuntimeError(f"SF export failed: {result.stderr}")
        export_path = Path(export_dir)
        csv_files = list(export_path.glob("**/internal_all.csv"))
        if csv_files:
            return str(csv_files[0])
        all_csvs = list(export_path.glob("**/*.csv"))
        if all_csvs:
            return str(all_csvs[0])
        raise RuntimeError(f"No CSV file found in export directory: {export_dir}")
