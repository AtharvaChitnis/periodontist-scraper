"""Validation of extracted periodontist records."""

from __future__ import annotations

import re

from .models import PeriodontistRecord

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
PHONE_RE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
EXPERIENCE_RE = re.compile(r"^\d{1,2}$")


class RecordValidator:
    def is_valid(self, record: PeriodontistRecord) -> bool:
        if not (record.name or record.email or record.phone or record.registration_number):
            return False
        if record.name and len(record.name.strip()) < 3:
            return False
        if record.email and not EMAIL_RE.match(record.email):
            return False
        if record.phone:
            digits = re.sub(r"\D", "", record.phone)
            if len(digits) < 10 and not PHONE_RE.match(record.phone):
                return False
        if record.registration_year and not YEAR_RE.match(str(record.registration_year)):
            return False
        if record.experience_years and not EXPERIENCE_RE.match(str(record.experience_years)):
            return False
        return True

    def filter(self, records: list[PeriodontistRecord]) -> list[PeriodontistRecord]:
        valid: list[PeriodontistRecord] = []
        for record in records:
            if self.is_valid(record):
                record.ensure_provider_id()
                valid.append(record)
        return valid
