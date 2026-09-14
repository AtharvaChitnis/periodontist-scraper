"""Page downloader using requests, with robots.txt and polite delays."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from .models import PageDocument


class PageDownloader:
    def __init__(self, config: dict[str, Any], session: requests.Session | None = None) -> None:
        self.config = config
        self.timeout = int(config.get("timeout_seconds") or 20)
        self.delay = float(config.get("request_delay_seconds") or 1.5)
        self.user_agent = config.get("user_agent") or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.respect_robots = bool(config.get("respect_robots_txt", True))
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request_at = 0.0

    def fetch(self, url: str) -> PageDocument:
        if self.respect_robots and not self.can_fetch(url):
            return PageDocument(url=url, status_code=0, html="", fetch_error="blocked_by_robots_txt")
        self._throttle()
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            content_type = (response.headers.get("Content-Type") or "").lower()
            if response.status_code >= 400:
                return PageDocument(
                    url=str(response.url),
                    status_code=response.status_code,
                    html="",
                    fetch_error=f"http_{response.status_code}",
                )
            if "html" not in content_type and not response.text.lstrip().lower().startswith("<"):
                return PageDocument(
                    url=str(response.url),
                    status_code=response.status_code,
                    html="",
                    fetch_error="not_html",
                )
            return PageDocument(
                url=str(response.url),
                status_code=response.status_code,
                html=response.text,
                headers={k: v for k, v in response.headers.items()},
            )
        except requests.RequestException as exc:
            return PageDocument(url=url, status_code=0, html="", fetch_error=str(exc))

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        parser = self._robots[origin]
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    def _load_robots(self, origin: str) -> RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        try:
            self._throttle()
            response = self.session.get(robots_url, timeout=self.timeout)
            if response.status_code >= 400:
                return None
            parser.parse(response.text.splitlines())
            return parser
        except requests.RequestException:
            return None

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_at = time.monotonic()
