"""Search API + extraction for the U.S. NPI Registry (CMS NPPES)."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .models import PeriodontistRecord, utc_today
from .registry_catalog import get_registry

NPI_API = "https://npiregistry.cms.hhs.gov/api/"
NPI_VIEW = "https://npiregistry.cms.hhs.gov/provider-view/{npi}"
PERIODONTICS_TAXONOMY = "1223P0300X"
PERIODONTICS_DESCRIPTION = "Periodontics"
MAX_SKIP = 1000
PAGE_SIZE = 200

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]


class NPIRegistryClient:
    """Official CMS NPI Registry API 2.1 — no API key required."""

    def __init__(self, config: dict[str, Any], session: requests.Session | None = None) -> None:
        self.config = config
        self.timeout = int(config.get("timeout_seconds") or 20)
        self.delay = float(config.get("request_delay_seconds") or 1.0)
        self.user_agent = config.get("user_agent") or "PeriodontistDirectoryBot/1.0"
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
        )
        self._last_request_at = 0.0
        meta = get_registry("npi") or {}
        self.registry_name = meta.get("registry") or "NPI Registry"

    def search(self, query: str | None = None) -> list[dict[str, Any]]:
        """Search API layer: paginated NPI queries for periodontists."""
        max_results = int(self.config.get("max_results") or PAGE_SIZE)
        state = (self.config.get("state") or "").strip().upper()
        city = (self.config.get("city") or "").strip()
        last_name = (self.config.get("last_name") or "").strip()
        first_name = (self.config.get("first_name") or "").strip()
        if query and " " in query and not last_name:
            parts = query.split()
            if parts[-1].lower() not in {"periodontist", "periodontics", "dentist"}:
                last_name = parts[-1]

        if self.config.get("all_states"):
            hits: list[dict[str, Any]] = []
            for code in US_STATES:
                if len(hits) >= max_results:
                    break
                remaining = max_results - len(hits)
                hits.extend(
                    self._paginate(
                        limit=remaining,
                        state=code,
                        city=city,
                        first_name=first_name,
                        last_name=last_name,
                    )
                )
            return hits[:max_results]
        return self._paginate(
            limit=max_results,
            state=state,
            city=city,
            first_name=first_name,
            last_name=last_name,
        )

    def extract(self, hits: list[dict[str, Any]]) -> list[PeriodontistRecord]:
        records: list[PeriodontistRecord] = []
        for hit in hits:
            raw = hit.get("payload")
            if not isinstance(raw, dict):
                continue
            record = self.map_result(raw)
            if record:
                records.append(record)
        return records

    def discover_urls(self, hits: list[dict[str, Any]]) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for hit in hits:
            url = hit.get("url") or ""
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def map_result(self, item: dict[str, Any]) -> PeriodontistRecord | None:
        basic = item.get("basic") or {}
        if str(basic.get("status") or "A").upper() not in {"A", "ACTIVE", ""}:
            return None
        npi = str(item.get("number") or "").strip()
        if not npi:
            return None
        first = _title_case(basic.get("first_name") or "")
        last = _title_case(basic.get("last_name") or "")
        prefix = str(basic.get("name_prefix") or "").strip(" -")
        if prefix in {"--", "-", "None"}:
            prefix = "Dr."
        if prefix.lower() == "dr.":
            prefix = "Dr."
        name = " ".join(part for part in (prefix if prefix else "Dr.", first, last) if part).strip()
        taxonomy = _primary_taxonomy(item.get("taxonomies") or [])
        location = _best_address(item.get("addresses") or [])
        credential = str(basic.get("credential") or "").strip(" -")
        enumeration = str(basic.get("enumeration_date") or "")
        reg_year = enumeration[:4] if enumeration[:4].isdigit() else ""
        license_no = str(taxonomy.get("license") or "").strip()
        email = _email_from_endpoints(item.get("endpoints") or [])
        phone = _format_phone(location.get("telephone_number") or "")
        record = PeriodontistRecord(
            provider_id=npi,
            name=name,
            first_name=first,
            last_name=last,
            profession="Dentist",
            job_title="Periodontist",
            specialty="Periodontics",
            subspecialty=str(taxonomy.get("desc") or "Dentist, Periodontics"),
            qualification=credential,
            registration_number=npi,
            registration_year=reg_year,
            experience_years=_years_since(reg_year),
            clinic_name=_title_case(location.get("organization_name") or ""),
            hospital="",
            address=_format_address(location),
            city=_title_case(location.get("city") or ""),
            state=str(location.get("state") or taxonomy.get("state") or "").upper(),
            country=_country_name(location.get("country_code") or location.get("country_name") or "US"),
            phone=phone,
            email=email,
            website=NPI_VIEW.format(npi=npi),
            source_registry=self.registry_name,
            source_url=NPI_VIEW.format(npi=npi),
            last_verified=utc_today(),
        )
        if license_no and license_no not in {npi, "--"} and not record.qualification:
            record.qualification = license_no
        return record

    def _paginate(
        self,
        limit: int,
        state: str = "",
        city: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        skip = 0
        while len(hits) < limit and skip <= MAX_SKIP:
            page_limit = min(PAGE_SIZE, limit - len(hits), 200)
            params: dict[str, Any] = {
                "version": "2.1",
                "taxonomy_description": PERIODONTICS_DESCRIPTION,
                "enumeration_type": "NPI-1",
                "limit": page_limit,
                "skip": skip,
            }
            if state:
                params["state"] = state
            if city:
                params["city"] = city
            if first_name:
                params["first_name"] = first_name
            if last_name:
                params["last_name"] = last_name
            payload = self._get(params)
            results = payload.get("results") or []
            if not results:
                break
            for item in results:
                npi = str(item.get("number") or "")
                hits.append(
                    {
                        "title": f"{(item.get('basic') or {}).get('first_name', '')} {(item.get('basic') or {}).get('last_name', '')}".strip(),
                        "url": NPI_VIEW.format(npi=npi) if npi else "",
                        "payload": item,
                    }
                )
                if len(hits) >= limit:
                    break
            skip += len(results)
            if len(results) < page_limit:
                break
        return hits

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        self._throttle()
        response = self.session.get(NPI_API, params=params, timeout=self.timeout)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError:
            return {"results": []}
        if not isinstance(data, dict):
            return {"results": []}
        return data

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_at = time.monotonic()


def _primary_taxonomy(taxonomies: list[dict[str, Any]]) -> dict[str, Any]:
    if not taxonomies:
        return {}
    for item in taxonomies:
        if item.get("primary") and PERIODONTICS_TAXONOMY in str(item.get("code") or ""):
            return item
    for item in taxonomies:
        if PERIODONTICS_TAXONOMY in str(item.get("code") or "") or "periodont" in str(item.get("desc") or "").lower():
            return item
    for item in taxonomies:
        if item.get("primary"):
            return item
    return taxonomies[0]


def _best_address(addresses: list[dict[str, Any]]) -> dict[str, Any]:
    if not addresses:
        return {}
    for item in addresses:
        if str(item.get("address_purpose") or "").upper() == "LOCATION":
            return item
    return addresses[-1]


def _email_from_endpoints(endpoints: list[dict[str, Any]]) -> str:
    for item in endpoints:
        endpoint = str(item.get("endpoint") or item.get("endpointType") or "")
        if "@" in endpoint:
            return endpoint.strip().lower()
        if "email" in str(item.get("endpointType") or item.get("endpointTypeDescription") or "").lower():
            value = str(item.get("endpoint") or "").strip().lower()
            if "@" in value:
                return value
    return ""


def _format_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return (value or "").strip()
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _format_address(location: dict[str, Any]) -> str:
    street = " ".join(
        part for part in (_title_case(location.get("address_1") or ""), _title_case(location.get("address_2") or "")) if part
    )
    city = _title_case(location.get("city") or "")
    state = str(location.get("state") or "").upper()
    postal = _format_postal(str(location.get("postal_code") or ""))
    country = _country_name(location.get("country_code") or location.get("country_name") or "")
    parts = [p for p in (street, city, " ".join(x for x in (state, postal) if x), country) if p]
    return ", ".join(parts)


def _format_postal(postal: str) -> str:
    digits = re.sub(r"\D", "", postal or "")
    if len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"
    return digits or postal


def _country_name(value: str) -> str:
    raw = (value or "").strip()
    if raw.upper() in {"US", "USA", "UNITED STATES"}:
        return "United States"
    return raw.title() if raw.isupper() else raw


def _years_since(year: str) -> str:
    if not year.isdigit():
        return ""
    current = datetime.now(timezone.utc).year
    delta = current - int(year)
    if delta < 0 or delta > 80:
        return ""
    return str(delta)


def _title_case(value: str) -> str:
    text = " ".join(str(value or "").split())
    if not text or text in {"--", "-"}:
        return ""
    if not text.isupper() and not text.islower():
        return text
    return text.title()
