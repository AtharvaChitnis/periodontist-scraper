"""HTML parser layer wrapping BeautifulSoup."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup, Tag

from .models import PageDocument


class HTMLParser:
    def __init__(self, html: str, url: str = "") -> None:
        self.url = url
        self.soup = BeautifulSoup(html, "lxml")

    @classmethod
    def from_page(cls, page: PageDocument) -> "HTMLParser":
        parser = cls(page.html, page.url)
        if not page.title:
            page.title = parser.page_title()
        return parser

    def page_title(self) -> str:
        if self.soup.title and self.soup.title.string:
            return " ".join(self.soup.title.string.split())
        og = self.soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            return " ".join(str(og["content"]).split())
        h1 = self.soup.find("h1")
        return " ".join(h1.get_text(" ", strip=True).split()) if h1 else ""

    def visible_text(self) -> str:
        for tag in self.soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        return " ".join(self.soup.get_text(" ", strip=True).split())

    def mailto_addresses(self) -> list[str]:
        emails: list[str] = []
        for anchor in self.soup.select('a[href^="mailto:"]'):
            href = anchor.get("href", "")
            email = href.split(":", 1)[-1].split("?", 1)[0].strip()
            if email:
                emails.append(email)
        return emails

    def tel_numbers(self) -> list[str]:
        numbers: list[str] = []
        for anchor in self.soup.select('a[href^="tel:"]'):
            href = anchor.get("href", "")
            numbers.append(href.split(":", 1)[-1].strip())
        return numbers

    def json_ld_nodes(self) -> list[dict]:
        nodes: list[dict] = []
        for script in self.soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
            raw = script.string or script.get_text() or ""
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            nodes.extend(_flatten_jsonld(payload))
        return nodes

    def meta_content(self, *names: str) -> str:
        for name in names:
            tag = self.soup.find("meta", attrs={"name": name}) or self.soup.find("meta", attrs={"property": name})
            if isinstance(tag, Tag) and tag.get("content"):
                return str(tag.get("content")).strip()
        return ""

    def itemprop(self, name: str) -> str:
        tag = self.soup.find(attrs={"itemprop": name})
        if not isinstance(tag, Tag):
            return ""
        content = tag.get("content")
        if content:
            return str(content).strip()
        href = tag.get("href") or ""
        if str(href).startswith("mailto:"):
            return str(href).split(":", 1)[-1].split("?", 1)[0]
        if str(href).startswith("tel:"):
            return str(href).split(":", 1)[-1]
        return " ".join(tag.get_text(" ", strip=True).split())

    def definition_list(self) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for dt in self.soup.find_all("dt"):
            key = " ".join(dt.get_text(" ", strip=True).split()).lower()
            dd = dt.find_next_sibling("dd")
            if key and isinstance(dd, Tag):
                pairs[key] = " ".join(dd.get_text(" ", strip=True).split())
        return pairs


def _flatten_jsonld(payload: object) -> list[dict]:
    nodes: list[dict] = []
    if isinstance(payload, list):
        for item in payload:
            nodes.extend(_flatten_jsonld(item))
        return nodes
    if not isinstance(payload, dict):
        return nodes
    graph = payload.get("@graph")
    if isinstance(graph, list):
        nodes.extend(_flatten_jsonld(graph))
    nodes.append(payload)
    return nodes
