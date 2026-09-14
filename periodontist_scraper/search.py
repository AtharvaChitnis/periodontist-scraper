"""Search API layer: discover candidate result pages for a query."""

from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests

from .models import PageDocument


class SearchAPI:
    """Thin search adapter. Default provider is DuckDuckGo HTML (no API key)."""

    DDG_URL = "https://html.duckduckgo.com/html/"
    DDG_LITE = "https://lite.duckduckgo.com/lite/"

    def __init__(self, config: dict[str, Any], session: requests.Session | None = None) -> None:
        self.config = config
        search_cfg = config.get("search") or {}
        self.provider = (search_cfg.get("provider") or "duckduckgo").lower()
        self.custom_search_url = search_cfg.get("custom_search_url") or ""
        self.timeout = int(config.get("timeout_seconds") or 20)
        self.user_agent = config.get("user_agent") or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent, "Accept-Language": "en-US,en;q=0.9"})

    def search(self, query: str | None = None) -> list[dict[str, str]]:
        q = self._build_query(query)
        if self.provider == "custom" and self.custom_search_url:
            return self._search_custom(q)
        return self._search_duckduckgo(q)

    def _build_query(self, query: str | None) -> str:
        base = query or self.config.get("query") or "periodontist"
        extras: list[str] = []
        for key in ("city", "state", "location", "last_name"):
            value = str(self.config.get(key) or "").strip()
            if value and value.lower() not in base.lower():
                extras.append(value)
        return " ".join([base, *extras]).strip()

    def _search_duckduckgo(self, query: str) -> list[dict[str, str]]:
        max_results = int(self.config.get("max_results") or 25)
        try:
            response = self.session.post(
                self.DDG_URL,
                data={"q": query},
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = self._parse_duckduckgo(response.text, max_results)
        except requests.RequestException:
            results = []
        if results:
            return results
        lite = self.session.get(self.DDG_LITE, params={"q": query}, timeout=self.timeout)
        lite.raise_for_status()
        return self._parse_generic_links(lite.text, max_results)

    def _search_custom(self, query: str) -> list[dict[str, str]]:
        url = self.custom_search_url.format(query=requests.utils.quote(query))
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return self._parse_generic_links(response.text, int(self.config.get("max_results") or 25))

    def _parse_duckduckgo(self, html: str, limit: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for match in re.finditer(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = html_lib.unescape(match.group(1))
            title = re.sub(r"<[^>]+>", "", html_lib.unescape(match.group(2))).strip()
            url = self._unwrap_ddg_url(href)
            if not url:
                continue
            results.append({"title": title, "url": url})
            if len(results) >= limit:
                break
        if not results:
            results = self._parse_generic_links(html, limit)
        return results

    def _parse_generic_links(self, html: str, limit: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL):
            href = html_lib.unescape(match.group(1)).strip()
            if href.startswith("//"):
                href = "https:" + href
            if not href.startswith("http"):
                continue
            title = re.sub(r"<[^>]+>", "", html_lib.unescape(match.group(2))).strip()
            if href in seen:
                continue
            seen.add(href)
            results.append({"title": title or href, "url": href})
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _unwrap_ddg_url(href: str) -> str:
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            uddg = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(uddg)
        if href.startswith("//"):
            return "https:" + href
        return href


def search_from_local_index(index_html: str, base_url: str = "https://local.example") -> list[dict[str, str]]:
    """Offline/demo helper: treat an HTML file as a search result page."""
    api = SearchAPI({"max_results": 50, "timeout_seconds": 5, "user_agent": "demo"})
    results = api._parse_generic_links(index_html, 50)
    for item in results:
        if item["url"].startswith("/"):
            item["url"] = urljoin(base_url, item["url"])
    return results


def page_from_response(url: str, response: requests.Response) -> PageDocument:
    return PageDocument(url=url, status_code=response.status_code, html=response.text)
