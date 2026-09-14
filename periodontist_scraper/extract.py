"""Information extraction for the periodontist schema."""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlparse

from .models import PageDocument, PeriodontistRecord, utc_today
from .parser import HTMLParser


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})")
NAME_RE = re.compile(
    r"\b(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)"
    r"(?:,?\s*(?:DDS|DMD|MS|PhD|MD))?\b"
)
CREDENTIAL_RE = re.compile(r"\b(DDS|DMD|MS|PhD|MD|BDS|MDS|FACS|FACD)\b", re.IGNORECASE)
TITLE_RE = re.compile(
    r"(board[-\s]?certified\s+periodontist|periodontist|periodontal surgeon|"
    r"dental implant specialist|gum specialist)",
    re.IGNORECASE,
)
SUBSPECIALTY_RE = re.compile(
    r"(dental implants?|implant dentistry|gum grafting|regenerative(?: periodontal)? surgery|"
    r"periodontal plastic surgery|laser periodontics|osseous surgery)",
    re.IGNORECASE,
)
EXPERIENCE_RE = re.compile(
    r"(\d{1,2}\+?\s+years?(?:\s+of)?\s+experience|"
    r"(?:over|more than)\s+\d{1,2}\s+years|"
    r"practicing since\s+(?:19|20)\d{2}|"
    r"since\s+(?:19|20)\d{2})",
    re.IGNORECASE,
)
REG_NUMBER_RE = re.compile(
    r"(?:license|registration(?:\s+number)?|gdc|npi|dci)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-]{3,20})",
    re.IGNORECASE,
)
NPI_RE = re.compile(r"\bNPI\s*(?:number|#|:)?\s*(\d{10})\b", re.IGNORECASE)
REG_YEAR_RE = re.compile(
    r"(?:registration year|licensed since|issued|license year)\s*[:#]?\s*((?:19|20)\d{2})",
    re.IGNORECASE,
)
HOSPITAL_RE = re.compile(r"\b([A-Z][A-Za-z .'-]+Hospital)\b")
CLINIC_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9](?:[A-Za-z0-9][A-Za-z0-9 .'-]{0,40})?(?:Periodontics|Perio|Dental(?: Care)?|Implants|Associates|Clinic|Center))\b"
)
ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9 .'-]+(?:,\s*[A-Za-z .'-]+){1,3}(?:,\s*(?:[A-Z]{2}|\d{5}(?:-\d{4})?))?"
)
CITY_STATE_RE = re.compile(r"([A-Z][A-Za-z.' ]+?),\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?")
_LABEL_NAMES = (
    "clinic|hospital|address|city|state|country|phone|email|website|profession|"
    "job title|specialty|subspecialty|qualification|registration number|license|"
    "registration year|experience|contact"
)
LABELED_RE = re.compile(
    rf"({_LABEL_NAMES})\s*[:\-]\s*(.+?)(?=(?:\s+(?:{_LABEL_NAMES})\s*[:\-])|$)",
    re.IGNORECASE,
)
JUNK_EMAIL_PARTS = (
    "sentry.io",
    "wixpress.com",
    "cloudflare",
    "schema.org",
    "noreply",
    "no-reply",
    "privacy@",
    "webmaster@",
)

US_STATE_NAMES = {
    "al": "AL", "ak": "AK", "az": "AZ", "ar": "AR", "ca": "CA", "co": "CO", "ct": "CT",
    "de": "DE", "fl": "FL", "ga": "GA", "hi": "HI", "id": "ID", "il": "IL", "in": "IN",
    "ia": "IA", "ks": "KS", "ky": "KY", "la": "LA", "me": "ME", "md": "MD", "ma": "MA",
    "mi": "MI", "mn": "MN", "ms": "MS", "mo": "MO", "mt": "MT", "ne": "NE", "nv": "NV",
    "nh": "NH", "nj": "NJ", "nm": "NM", "ny": "NY", "nc": "NC", "nd": "ND", "oh": "OH",
    "ok": "OK", "or": "OR", "pa": "PA", "ri": "RI", "sc": "SC", "sd": "SD", "tn": "TN",
    "tx": "TX", "ut": "UT", "vt": "VT", "va": "VA", "wa": "WA", "wv": "WV", "wi": "WI",
    "wy": "WY", "dc": "DC",
}


class InformationExtractor:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.source_registry = str(self.config.get("source_registry") or "web_search")
        self.default_country = str(self.config.get("default_country") or "United States")

    def extract(self, page: PageDocument) -> list[PeriodontistRecord]:
        if not page.html:
            return []
        parser = HTMLParser.from_page(page)
        jsonld = parser.json_ld_nodes()
        text = parser.visible_text()
        labels = self._labeled_fields(text)
        labels.update(parser.definition_list())
        self._apply_itemprop(labels, parser)
        emails = self._unique(self._clean_emails(parser.mailto_addresses() + EMAIL_RE.findall(text)))
        phones = self._unique(self._clean_phones(parser.tel_numbers() + PHONE_RE.findall(text)))
        jsonld_people = [node for node in jsonld if self._is_person_like(node)]

        records: list[PeriodontistRecord] = []
        if jsonld_people:
            for person in jsonld_people:
                records.append(self._from_jsonld(person, page, emails, phones, text, parser, labels))
        else:
            records.append(self._from_page_heuristics(page, parser, text, emails, phones, labels))

        out: list[PeriodontistRecord] = []
        npi_match = NPI_RE.search(text)
        for record in records:
            if npi_match and not record.registration_number:
                record.registration_number = npi_match.group(1)
            self._finalize(record, page, parser)
            if record.name or record.email or record.phone:
                out.append(record)
        return out

    def _from_jsonld(
        self,
        person: dict,
        page: PageDocument,
        emails: list[str],
        phones: list[str],
        text: str,
        parser: HTMLParser,
        labels: dict[str, str],
    ) -> PeriodontistRecord:
        name = str(person.get("name") or "").strip()
        email = self._first(self._clean_emails(_as_list(person.get("email"))) + emails)
        email = email or self._from_label(labels, "email") or self._email_from_contact(labels)
        phone = self._first(self._clean_phones(_as_list(person.get("telephone")) + phones))
        title = self._occupation(person) or self._job_title(text, parser.page_title(), labels)
        address = self._address_from_jsonld(person)
        works_for = person.get("worksFor") or person.get("affiliation") or {}
        if isinstance(works_for, list):
            works_for = works_for[0] if works_for else {}
        clinic = ""
        if isinstance(works_for, dict):
            clinic = str(works_for.get("name") or "")
            if not address["address"]:
                address = self._address_from_jsonld(works_for) or address
        website = str(person.get("url") or "")
        specialty = str(person.get("medicalSpecialty") or person.get("specialty") or "")
        if isinstance(person.get("medicalSpecialty"), dict):
            specialty = str(person["medicalSpecialty"].get("name") or specialty)
        experience_raw = self._experience_text(text, person, labels)
        return PeriodontistRecord(
            name=name or self._name_from_text(parser.page_title(), text),
            phone=phone or self._from_label(labels, "phone"),
            email=email or self._from_label(labels, "email"),
            job_title=self._normalize_title(title),
            specialty=self._specialty(specialty, text, labels),
            clinic_name=clinic or self._clinic_name(text, labels, parser.page_title()),
            address=address["address"] or self._from_label(labels, "address"),
            city=address["city"] or self._from_label(labels, "city"),
            state=address["state"] or self._from_label(labels, "state"),
            country=address["country"] or self._from_label(labels, "country"),
            website=website,
            experience_years=self._experience_years(experience_raw, text, labels),
            qualification=self._qualification(text, labels, name),
            **self._common_text_fields(text, labels, parser.page_title()),
        )

    def _from_page_heuristics(
        self,
        page: PageDocument,
        parser: HTMLParser,
        text: str,
        emails: list[str],
        phones: list[str],
        labels: dict[str, str],
    ) -> PeriodontistRecord:
        title = parser.page_title()
        name = self._name_from_text(title, text)
        experience_raw = self._experience_text(text, {}, labels)
        city, state = self._city_state(text, labels)
        return PeriodontistRecord(
            name=name,
            phone=self._first(phones) or self._from_label(labels, "phone"),
            email=self._first(emails) or self._from_label(labels, "email") or self._email_from_contact(labels),
            job_title=self._job_title(text, title, labels),
            specialty=self._specialty("", text, labels),
            clinic_name=self._clinic_name(text, labels, title),
            address=self._from_label(labels, "address") or self._address_from_text(text),
            city=city,
            state=state,
            country=self._from_label(labels, "country"),
            website=self._website(page.url, text, labels, parser),
            experience_years=self._experience_years(experience_raw, text, labels),
            qualification=self._qualification(text, labels, name),
            **self._common_text_fields(text, labels, title),
        )

    def _common_text_fields(self, text: str, labels: dict[str, str], page_title: str) -> dict[str, str]:
        return {
            "profession": self._profession(text, labels),
            "subspecialty": self._subspecialty(text, labels),
            "registration_number": self._registration_number(text, labels),
            "registration_year": self._registration_year(text, labels),
            "hospital": self._hospital(text, labels),
        }

    def _finalize(self, record: PeriodontistRecord, page: PageDocument, parser: HTMLParser) -> None:
        record.source_url = record.source_url or page.url
        record.source_registry = record.source_registry or self._registry_from_url(page.url)
        record.last_verified = record.last_verified or utc_today()
        record.website = record.website or self._origin(page.url)
        record.specialty = record.specialty or "Periodontics"
        record.profession = record.profession or "Dentist"
        record.country = record.country or self.default_country
        if record.country in {"US", "USA", "United States of America"}:
            record.country = "United States"
        record.job_title = record.job_title or "Periodontist"
        first, last = self._split_name(record.name)
        record.first_name = record.first_name or first
        record.last_name = record.last_name or last
        if not record.qualification:
            record.qualification = self._qualification("", {}, record.name)
        if record.address and (not record.city or not record.state):
            city, state = self._city_state(record.address, {})
            record.city = record.city or city
            record.state = record.state or state
        record.ensure_provider_id()

    def _name_from_text(self, title: str, text: str) -> str:
        doctor = re.search(
            r"\bDr\.?\s+[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][a-z]+\b",
            f"{title} {text[:1500]}",
        )
        if doctor:
            return doctor.group(0).strip()
        for source in (title, text[:1500]):
            match = NAME_RE.search(source or "")
            if match:
                name = match.group(1).strip(" ,")
                if not self._looks_like_clinic_name(name):
                    return name
        return title.split("|")[0].split("-")[0].strip() if title else ""

    def _split_name(self, name: str) -> tuple[str, str]:
        cleaned = re.sub(r"\bDr\.?\b", "", name or "", flags=re.IGNORECASE)
        cleaned = CREDENTIAL_RE.sub("", cleaned)
        cleaned = re.sub(r"\b(Periodontist|Dentist|Physician)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[,.]", " ", cleaned)
        parts = [p for p in cleaned.split() if p]
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[-1]

    def _job_title(self, text: str, page_title: str, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "job title")
        if labeled:
            return self._normalize_title(labeled)
        blob = f"{page_title} {text[:2000]}"
        match = TITLE_RE.search(blob)
        if match:
            return self._normalize_title(match.group(0))
        return "Periodontist" if "periodont" in blob.lower() else ""

    def _profession(self, text: str, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "profession")
        if labeled:
            return labeled.title() if labeled.lower() != "dds" else "Dentist"
        blob = text.lower()
        if "periodont" in blob or "dentist" in blob:
            return "Dentist"
        return "Dentist"

    def _specialty(self, specialty: str, text: str, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "specialty") or specialty
        if labeled:
            return labeled.replace("https://schema.org/", "").strip().title()
        return "Periodontics" if "periodont" in text.lower() else labeled

    def _subspecialty(self, text: str, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "subspecialty")
        if labeled:
            return labeled.strip().rstrip(".").capitalize() if labeled.islower() else labeled
        aliases = {
            "dental implant": "Dental implants",
            "dental implants": "Dental implants",
            "implant dentistry": "Implant dentistry",
            "gum grafting": "Gum grafting",
            "regenerative surgery": "Regenerative periodontal surgery",
            "regenerative periodontal surgery": "Regenerative periodontal surgery",
            "periodontal plastic surgery": "Periodontal plastic surgery",
            "laser periodontics": "Laser periodontics",
            "osseous surgery": "Osseous surgery",
        }
        found: list[str] = []
        seen: set[str] = set()
        for match in SUBSPECIALTY_RE.finditer(text or ""):
            canonical = aliases.get(match.group(0).lower(), match.group(0)[0].upper() + match.group(0)[1:].lower())
            if canonical not in seen:
                seen.add(canonical)
                found.append(canonical)
        return ", ".join(found)

    def _qualification(self, text: str, labels: dict[str, str], name: str) -> str:
        labeled = self._from_label(labels, "qualification")
        found = [m.group(0).upper() for m in CREDENTIAL_RE.finditer(" ".join([labeled, name, text[:800]]))]
        return ", ".join(self._unique(found))

    def _registration_number(self, text: str, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "registration number") or self._from_label(labels, "license")
        if labeled:
            match = re.search(r"[A-Z0-9][A-Z0-9\-]{3,}", labeled, re.IGNORECASE)
            return match.group(0).upper() if match else labeled
        match = REG_NUMBER_RE.search(text or "")
        return match.group(1).upper() if match else ""

    def _registration_year(self, text: str, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "registration year")
        if labeled and re.fullmatch(r"(19|20)\d{2}", labeled.strip()):
            return labeled.strip()
        match = REG_YEAR_RE.search(text or "")
        if match:
            return match.group(1)
        number_line = REG_NUMBER_RE.search(text or "")
        if number_line:
            year = re.search(r"(19|20)\d{2}", text[number_line.end() : number_line.end() + 40] or "")
            if year:
                return year.group(0)
        return ""

    def _experience_text(self, text: str, person: dict, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "experience")
        if labeled:
            return labeled
        for key in ("yearsOfExperience", "experience", "description"):
            value = person.get(key)
            if isinstance(value, (int, float)):
                return f"{int(value)} years of experience"
            if isinstance(value, str):
                match = EXPERIENCE_RE.search(value)
                if match:
                    return match.group(0)
        match = EXPERIENCE_RE.search(text or "")
        return match.group(0) if match else ""

    def _experience_years(self, raw: str, text: str, labels: dict[str, str]) -> str:
        blob = " ".join([raw, self._from_label(labels, "experience"), text[:1500]])
        since = re.search(r"(?:practicing\s+)?since\s+((?:19|20)\d{2})", blob, re.IGNORECASE)
        count = re.search(r"(?:over|more than)?\s*(\d{1,2})\+?\s+years", blob, re.IGNORECASE)
        if count:
            return count.group(1)
        if since:
            try:
                years = int(utc_today()[:4]) - int(since.group(1))
                return str(max(years, 0))
            except ValueError:
                return ""
        return ""

    def _clinic_name(self, text: str, labels: dict[str, str], page_title: str) -> str:
        labeled = self._from_label(labels, "clinic")
        for source in (labeled, page_title or "", text[:1500] or ""):
            match = CLINIC_RE.search(source)
            if match:
                return match.group(1).strip(" -|")
        return labeled.split(".")[0].strip() if labeled else ""

    def _hospital(self, text: str, labels: dict[str, str]) -> str:
        labeled = self._from_label(labels, "hospital")
        blob = labeled or text or ""
        match = HOSPITAL_RE.search(blob)
        return match.group(1).strip() if match else labeled

    def _address_from_text(self, text: str) -> str:
        match = ADDRESS_RE.search(text or "")
        return match.group(0).strip() if match else ""

    def _city_state(self, text: str, labels: dict[str, str]) -> tuple[str, str]:
        city = self._from_label(labels, "city")
        state = self._normalize_state(self._from_label(labels, "state"))
        match = CITY_STATE_RE.search(text or "")
        if match:
            city = city or match.group(1).strip()
            state = state or match.group(2)
        return city, state

    def _website(self, page_url: str, text: str, labels: dict[str, str], parser: HTMLParser) -> str:
        labeled = self._from_label(labels, "website")
        if labeled and labeled.startswith("http"):
            return labeled
        canonical = parser.soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
        if canonical and canonical.get("href"):
            return str(canonical["href"])
        return self._origin(page_url)

    def _registry_from_url(self, url: str) -> str:
        host = urlparse(url).netloc.lower()
        mapping = {
            "healthgrades.com": "healthgrades",
            "zocdoc.com": "zocdoc",
            "vitals.com": "vitals",
            "npi": "npi_registry",
        }
        for token, name in mapping.items():
            if token in host:
                return name
        return self.source_registry

    def _address_from_jsonld(self, node: dict) -> dict[str, str]:
        empty = {"address": "", "city": "", "state": "", "country": ""}
        raw = node.get("address")
        if isinstance(raw, str):
            city, state = self._city_state(raw, {})
            return {"address": raw, "city": city, "state": state, "country": ""}
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        if not isinstance(raw, dict):
            return empty
        street = str(raw.get("streetAddress") or "")
        city = str(raw.get("addressLocality") or "")
        state = self._normalize_state(str(raw.get("addressRegion") or ""))
        postal = str(raw.get("postalCode") or "")
        country = str(raw.get("addressCountry") or "")
        if country in {"US", "USA"}:
            country = "United States"
        parts = [p for p in (street, city, " ".join(x for x in (state, postal) if x), country) if p]
        return {"address": ", ".join(parts), "city": city, "state": state, "country": country}

    def _occupation(self, person: dict) -> str:
        title = str(person.get("jobTitle") or "")
        occupation = person.get("hasOccupation")
        if isinstance(occupation, dict):
            title = str(occupation.get("name") or title)
        return title

    def _apply_itemprop(self, labels: dict[str, str], parser: HTMLParser) -> None:
        mapping = {
            "name": parser.itemprop("name"),
            "telephone": parser.itemprop("telephone"),
            "email": parser.itemprop("email"),
            "jobtitle": parser.itemprop("jobTitle"),
            "address": parser.itemprop("address") or parser.itemprop("streetAddress"),
            "city": parser.itemprop("addressLocality"),
            "state": parser.itemprop("addressRegion"),
            "postal": parser.itemprop("postalCode"),
        }
        if mapping["name"] and "name" not in labels:
            labels["name"] = mapping["name"]
        if mapping["telephone"] and "phone" not in labels:
            labels["phone"] = mapping["telephone"]
        if mapping["email"] and "email" not in labels:
            labels["email"] = mapping["email"]
        if mapping["jobtitle"] and "job title" not in labels:
            labels["job title"] = mapping["jobtitle"]
        if mapping["address"] and "address" not in labels:
            labels["address"] = mapping["address"]
        if mapping["city"] and "city" not in labels:
            labels["city"] = mapping["city"]
        if mapping["state"] and "state" not in labels:
            labels["state"] = mapping["state"]

    def _labeled_fields(self, text: str) -> dict[str, str]:
        labels: dict[str, str] = {}
        for match in LABELED_RE.finditer(text or ""):
            key = match.group(1).strip().lower()
            value = match.group(2).strip().rstrip(".")
            if key not in labels and value:
                labels[key] = value
        return labels

    @staticmethod
    def _from_label(labels: dict[str, str], key: str) -> str:
        return " ".join((labels.get(key) or "").strip().split())

    def _email_from_contact(self, labels: dict[str, str]) -> str:
        contact = self._from_label(labels, "contact")
        match = EMAIL_RE.search(contact)
        return match.group(0).lower() if match else ""

    @staticmethod
    def _normalize_title(title: str) -> str:
        cleaned = " ".join((title or "").split())
        mapping = {
            "periodontist": "Periodontist",
            "board certified periodontist": "Board-Certified Periodontist",
            "board-certified periodontist": "Board-Certified Periodontist",
            "periodontal surgeon": "Periodontal Surgeon",
            "dental implant specialist": "Dental Implant Specialist",
            "gum specialist": "Gum Specialist",
        }
        return mapping.get(cleaned.lower(), cleaned.title() if cleaned else "")

    @staticmethod
    def _normalize_state(value: str) -> str:
        raw = (value or "").strip()
        if len(raw) == 2:
            return raw.upper()
        return US_STATE_NAMES.get(raw.lower(), raw)

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return url

    def _clean_emails(self, values: Iterable[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            email = (value or "").strip().strip(".,;<>").lower()
            if not EMAIL_RE.fullmatch(email):
                continue
            if any(part in email for part in JUNK_EMAIL_PARTS):
                continue
            cleaned.append(email)
        return cleaned

    def _clean_phones(self, values: Iterable[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            digits = re.sub(r"\D", "", value or "")
            if digits.startswith("1") and len(digits) == 11:
                digits = digits[1:]
            if len(digits) != 10:
                continue
            cleaned.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
        return cleaned

    @staticmethod
    def _is_person_like(node: dict) -> bool:
        types = node.get("@type")
        type_blob = " ".join(types if isinstance(types, list) else [str(types or "")]).lower()
        if "person" in type_blob or "physician" in type_blob or "dentist" in type_blob:
            return True
        return bool(node.get("jobTitle") and node.get("name"))

    @staticmethod
    def _looks_like_clinic_name(name: str) -> bool:
        lowered = name.lower()
        return any(
            token in lowered
            for token in ("clinic", "dental", "associates", "center", "group", "implants", "periodontics", "perio")
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    @staticmethod
    def _first(values: list[str]) -> str:
        return values[0] if values else ""


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
