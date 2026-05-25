"""Async page fetcher for source URL content extraction."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from internal_linking_tool.config import config


@dataclass
class PageMetadata:
    """Structured metadata extracted from a target page for anchor text generation."""
    title: str = ""
    h1: str = ""
    slug: str = ""
    description: str = ""


@dataclass
class FetchedPage:
    url: str
    status_code: int = 0
    text: str = ""
    raw_html: str = ""
    outlinks: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status_code == 200 and self.error is None


def extract_page_metadata(html: str, url: str) -> "PageMetadata":
    if not html:
        return PageMetadata()
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""
    slug = _slug_to_words(url)
    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = str(meta_desc["content"]).strip()
    return PageMetadata(title=title, h1=h1, slug=slug, description=description)


def _slug_to_words(url: str) -> str:
    from urllib.parse import urlparse
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    last_segment = path.split("/")[-1]
    return last_segment.replace("-", " ").replace("_", " ")


def extract_readable_text(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main:
        return main.get_text(separator=" ", strip=True)
    return soup.get_text(separator=" ", strip=True)


def extract_outlinks(html, base_domain=None):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"]).strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        parsed = urlparse(href)
        if parsed.netloc:
            if base_domain and parsed.netloc == base_domain:
                links.append(href)
        else:
            links.append(href)
    return links


class PageFetcher:
    def __init__(self, concurrency=None, timeout=None, user_agent=None):
        self.concurrency = concurrency or config.page_fetch_concurrency
        self.timeout = timeout or config.page_fetch_timeout_seconds
        self.user_agent = user_agent or config.page_fetch_user_agent

    async def fetch(self, url):
        headers = {"User-Agent": self.user_agent}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                html = response.text
                base_domain = urlparse(url).netloc
                return FetchedPage(
                    url=url, status_code=response.status_code,
                    text=extract_readable_text(html),
                    raw_html=html,
                    outlinks=extract_outlinks(html, base_domain=base_domain))
        except httpx.HTTPStatusError as e:
            return FetchedPage(url=url, status_code=e.response.status_code, error=str(e))
        except (httpx.RequestError, httpx.TimeoutException) as e:
            return FetchedPage(url=url, status_code=0, error=str(e))

    async def fetch_batch(self, urls):
        semaphore = asyncio.Semaphore(self.concurrency)

        async def _fetch_with_limit(url):
            async with semaphore:
                return await self.fetch(url)

        tasks = [_fetch_with_limit(url) for url in urls]
        return await asyncio.gather(*tasks)


async def fetch_page(url):
    fetcher = PageFetcher()
    return await fetcher.fetch(url)


async def fetch_pages(urls, concurrency=10):
    fetcher = PageFetcher(concurrency=concurrency)
    return await fetcher.fetch_batch(urls)
