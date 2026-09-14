"""End-to-end scrape pipeline matching the documented architecture."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any, Iterable

from .dedupe import Deduplicator
from .discovery import URLDiscovery
from .downloader import PageDownloader
from .export import DataExporter
from .extract import InformationExtractor
from .models import PageDocument, PeriodontistRecord
from .registry_catalog import get_registry, registry_host, scrapeable_registries
from .search import SearchAPI
from .validate import RecordValidator


class ScrapePipeline:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.search_api = SearchAPI(config)
        self.discovery = URLDiscovery(config)
        self.downloader = PageDownloader(config)
        self.extractor = InformationExtractor(config)
        self.validator = RecordValidator()
        self.deduplicator = Deduplicator()
        self.exporter = DataExporter()
        self.stats: dict[str, Any] = {
            "search_hits": 0,
            "pages_downloaded": 0,
            "html_extracted": 0,
            "fetch_errors": [],
        }

    def run(self, query: str | None = None) -> list[PeriodontistRecord]:
        """Search the web, download HTML, parse with BeautifulSoup, then extract."""
        search_query = self._compose_query(query)
        seed_urls = self._discover_urls(search_query)
        records = self._crawl(seed_urls)
        valid = self.validator.filter(records)
        return self.deduplicator.merge(valid)

    def run_local(self, html_paths: Iterable[str | Path]) -> list[PeriodontistRecord]:
        pages: list[PageDocument] = []
        for path in html_paths:
            file_path = Path(path)
            html = file_path.read_text(encoding="utf-8")
            pages.append(
                PageDocument(
                    url=file_path.resolve().as_uri(),
                    status_code=200,
                    html=html,
                    title=file_path.stem,
                )
            )
        records: list[PeriodontistRecord] = []
        for page in pages:
            records.extend(self.extractor.extract(page))
        self.stats["pages_downloaded"] = len(pages)
        self.stats["html_extracted"] = len(records)
        return self.deduplicator.merge(self.validator.filter(records))

    def export(self, records: list[PeriodontistRecord]) -> dict[str, str]:
        return self.exporter.export(records, self.config.get("output") or {})

    def _compose_query(self, query: str | None) -> str:
        parts = [query or self.config.get("query") or "periodontist"]
        for key in ("last_name", "city", "state", "location"):
            value = str(self.config.get(key) or "").strip()
            if value and value.lower() not in " ".join(parts).lower():
                parts.append(value)
        registry_id = (self.config.get("registry") or self.config.get("source_registry") or "").lower()
        if registry_id in {"npi", "npi_registry", "nppes"}:
            parts.append("periodontist")
        return " ".join(parts)

    def _discover_urls(self, query: str) -> list[str]:
        results: list[dict[str, str]] = []
        urls: list[str] = []
        seen: set[str] = set()
        targets = self._target_registries()
        for meta in targets:
            webpage = self.discovery.normalize(meta.get("webpage") or meta.get("official_url") or "")
            if webpage and webpage not in seen:
                seen.add(webpage)
                urls.append(webpage)
            host = registry_host(meta)
            if host:
                site_hits = self.search_api.search(f"{query} site:{host}")
                results.extend(site_hits)
                for url in self.discovery.discover(site_hits, host=host):
                    if url not in seen:
                        seen.add(url)
                        urls.append(url)
        open_hits = self.search_api.search(query)
        results.extend(open_hits)
        for url in self.discovery.discover(open_hits):
            if url not in seen:
                seen.add(url)
                urls.append(url)
        self.stats["search_hits"] = len(results)
        self.stats["registries"] = [item["id"] for item in targets]
        return urls[: int(self.config.get("max_pages") or 40)]

    def _target_registries(self) -> list[dict]:
        registry_id = (self.config.get("registry") or self.config.get("source_registry") or "web_search").lower()
        if registry_id in {"web_search", "all", "all_dental", ""}:
            preferred = [
                "npi",
                "uk_gdc",
                "uk_gdc_specialist",
                "au_dental_board",
                "au_ahpra",
                "nz_dental",
                "ie_dental",
                "sg_sdc",
                "in_ndc",
                "in_practo",
                "in_hpr",
            ]
            found = [get_registry(item_id) for item_id in preferred]
            return [item for item in found if item and item.get("webpage")]
        meta = get_registry(registry_id)
        if meta and meta.get("webpage") and not meta.get("skip_auto"):
            return [meta]
        return scrapeable_registries(True)[:8]

    def _crawl(self, seed_urls: list[str]) -> list[PeriodontistRecord]:
        max_pages = int(self.config.get("max_pages") or 40)
        queue = deque(seed_urls)
        seen: set[str] = set()
        records: list[PeriodontistRecord] = []
        fetched = 0
        errors: list[str] = []
        while queue and fetched < max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            page = self.downloader.fetch(url)
            fetched += 1
            if page.fetch_error or not page.html:
                if page.fetch_error:
                    errors.append(f"{url}: {page.fetch_error}")
                continue
            extracted = self.extractor.extract(page)
            records.extend(extracted)
            for extra in self.discovery.expand_from_html(page.url or url, page.html):
                if extra not in seen:
                    queue.append(extra)
        self.stats["pages_downloaded"] = fetched
        self.stats["html_extracted"] = len(records)
        self.stats["fetch_errors"] = errors[:12]
        return records
