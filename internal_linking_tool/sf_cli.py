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


def check_sf_installed(cli_path=None):
    path = cli_path or config.sf_cli_path
    return Path(path).exists()


class SfCliManager:
    def __init__(self, cli_path=None):
        self.cli_path = cli_path or config.sf_cli_path

    def _run(self, args, timeout=300):
        full_args = [self.cli_path] + args
        if "--headless" not in full_args:
            full_args.insert(1, "--headless")
        try:
            result = subprocess.run(full_args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"SF CLI command timed out after {timeout}s")
        except FileNotFoundError:
            raise RuntimeError(
                f"Screaming Frog CLI not found at '{self.cli_path}'. "
                "Install Screaming Frog or set SF_CLI_PATH.")
        if result.returncode != 0:
            stderr_lower = result.stderr.lower()
            if any(w in stderr_lower for w in ("gui", "locked", "database", "headless", "already running", "instance")):
                raise RuntimeError(
                    "Cannot access Screaming Frog. The GUI may be running. "
                    "Close the Screaming Frog application and try again.")
            raise RuntimeError(f"SF CLI error: {result.stderr.strip() or result.stdout.strip()}")
        return result

    def list_crawls(self) -> list[CrawlInfo]:
        result = self._run(["--list-crawls"])
        if not result.stdout.strip():
            return []
        crawls = []
        in_table = False
        for line in result.stdout.split("\n"):
            stripped = line.strip()
            if "Database Id" in stripped and "Name" in stripped:
                in_table = True
                continue
            if in_table and stripped.startswith("╚"):
                break
            if in_table and "║" in stripped and not stripped.startswith("╟") and not stripped.startswith("╠"):
                parts = [p.strip() for p in stripped.split("│") if p.strip()]
                if parts and parts[0].startswith("║"):
                    parts[0] = parts[0][1:].strip()
                if parts and parts[-1].endswith("║"):
                    parts[-1] = parts[-1][:-1].strip()
                if len(parts) >= 6:
                    try:
                        crawls.append(CrawlInfo(
                            id=parts[0],
                            name=parts[1] or "Untitled",
                            date=parts[6],
                            url_count=int(parts[4]) if parts[4].isdigit() else 0,
                        ))
                    except (ValueError, IndexError):
                        continue
        return crawls

    def start_crawl(self, url: str) -> str:
        result = self._run(["--crawl", url], timeout=config.crawl_timeout_seconds)
        match = re.search(r"crawl[_\s]?id[:\s]*([\w-]+)", result.stdout, re.IGNORECASE)
        if match:
            return match.group(1)
        return "unknown"

    def crawl_status(self, crawl_id: str) -> CrawlStatus:
        result = self._run(["--list-crawls"])
        for line in result.stdout.split("\n"):
            if crawl_id in line and "║" in line:
                parts = [p.strip() for p in line.split("║") if p.strip()]
                if len(parts) >= 6:
                    try:
                        url_count = int(parts[4]) if parts[4].isdigit() else 0
                        pct = parts[5] if parts[5].isdigit() else "0"
                        pct_val = float(pct)
                        phase = "completed" if pct_val >= 100 else "running"
                        return CrawlStatus(id=crawl_id, phase=phase, percent=pct_val, urls_crawled=url_count)
                    except (ValueError, IndexError):
                        pass
        return CrawlStatus(id=crawl_id, phase="unknown", percent=0.0, urls_crawled=0)

    def export_crawl_data(self, crawl_id, export_dir=None):
        if export_dir is None:
            export_dir = tempfile.mkdtemp(prefix="sf_export_")
        self._run([
            "--load-crawl", crawl_id,
            "--export-tabs", "Internal:All",
            "--output-folder", export_dir,
            "--export-format", "csv",
            "--overwrite",
        ], timeout=600)
        export_path = Path(export_dir)
        csv_files = list(export_path.glob("**/internal_all.csv"))
        if csv_files:
            return str(csv_files[0])
        all_csvs = list(export_path.glob("**/*.csv"))
        if all_csvs:
            return str(all_csvs[0])
        raise RuntimeError(f"No CSV file found in export directory: {export_dir}")
