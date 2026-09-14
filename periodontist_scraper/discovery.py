"""URL discovery: filter, normalize, and expand candidate pages."""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup


PERIODONTIST_HINTS = (
    "periodont",
    "perio",
    "gum specialist",
    "dental implant",
    "periodontal",
)


class URLDiscovery:
    def __init__(self, config: dict[str, Any]) -> None:
        self.allowed = [k.lower() for k in (config.get("allowed_url_keywords") or [])]
        self.blocked = [k.lower() for k in (config.get("blocked_url_keywords") or [])]
        self.allowed_hosts = [h.lower().lstrip(".") for h in (config.get("allowed_hosts") or []) if h]
        self.max_pages = int(config.get("max_pages") or 40)

    def discover(self, search_results: Iterable[dict[str, str]], host: str | None = None) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        host = (host or "").lower().lstrip(".")
        for result in search_results:
            url = self.normalize(result.get("url") or "")
            if not url or url in seen:
                continue
            if host:
                netloc = urlparse(url).netloc.lower()
                if host not in netloc:
                    continue
                if not self._not_blocked(url):
                    continue
            elif not self.is_allowed(url, result.get("title") or ""):
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= self.max_pages:
                break
        return urls

    def expand_from_html(self, page_url: str, html: str, extra_limit: int = 8) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        found: list[str] = []
        seen: set[str] = set()
        for anchor in soup.select("a[href]"):
            href = self.normalize(urljoin(page_url, anchor.get("href", "")))
            text = " ".join(anchor.get_text(" ", strip=True).split())
            if not href or href in seen:
                continue
            haystack = f"{href} {text}".lower()
            if not any(hint in haystack for hint in PERIODONTIST_HINTS):
                continue
            if not self.is_allowed(href, text):
                continue
            seen.add(href)
            found.append(href)
            if len(found) >= extra_limit:
                break
        return found

    def is_allowed(self, url: str, title: str = "") -> bool:
        blob = f"{url} {title}".lower()
        if not self._not_blocked(url, title):
            return False
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc.endswith("duckduckgo.com"):
            return False
        host = parsed.netloc.lower()
        if self.allowed_hosts and any(token in host for token in self.allowed_hosts):
            return True
        if self.allowed and not any(token in blob for token in self.allowed):
            return False
        return True

    def _not_blocked(self, url: str, title: str = "") -> bool:
        blob = f"{url} {title}".lower()
        return not any(blocked in blob for blocked in self.blocked)

    @staticmethod
    def normalize(url: str) -> str:
        url = (url or "").strip()
        if not url:
            return ""
        url, _frag = urldefrag(url)
        parsed = urlparse(url)
        if not parsed.netloc:
            return ""
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{parsed.scheme}://{parsed.netloc.lower()}{path}{query}"
