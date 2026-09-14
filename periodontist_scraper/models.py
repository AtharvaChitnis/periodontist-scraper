from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5


SCHEMA_FIELDS = [
    "provider_id",
    "name",
    "first_name",
    "last_name",
    "profession",
    "job_title",
    "specialty",
    "subspecialty",
    "qualification",
    "registration_number",
    "registration_year",
    "experience_years",
    "clinic_name",
    "hospital",
    "address",
    "city",
    "state",
    "country",
    "phone",
    "email",
    "website",
    "source_registry",
    "source_url",
    "last_verified",
]


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass
class PageDocument:
    url: str
    status_code: int = 0
    html: str = ""
    title: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    fetch_error: str = ""


@dataclass
class PeriodontistRecord:
    provider_id: str = ""
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    profession: str = ""
    job_title: str = ""
    specialty: str = ""
    subspecialty: str = ""
    qualification: str = ""
    registration_number: str = ""
    registration_year: str = ""
    experience_years: str = ""
    clinic_name: str = ""
    hospital: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    source_registry: str = ""
    source_url: str = ""
    last_verified: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: data.get(key, "") or "" for key in SCHEMA_FIELDS}

    def identity_key(self) -> str:
        registry = (self.source_registry or "").strip().lower()
        if self.registration_number:
            return f"reg:{self.registration_number.strip().lower()}|{registry}"
        if self.email:
            return f"email:{self.email.strip().lower()}"
        if self.phone:
            return f"phone:{self.phone.strip()}"
        name = (self.name or "").strip().lower()
        clinic = (self.clinic_name or "").strip().lower()
        return f"name:{name}|clinic:{clinic}|url:{(self.source_url or '').strip().lower()}"

    def ensure_provider_id(self) -> None:
        if not self.provider_id:
            self.provider_id = uuid5(NAMESPACE_URL, self.identity_key()).hex[:16]

    def completeness_score(self) -> int:
        return sum(1 for item in fields(self) if str(getattr(self, item.name) or "").strip())
