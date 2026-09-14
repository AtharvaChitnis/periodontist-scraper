"""Deduplicate periodontist records by email, phone, registration, or name."""

from __future__ import annotations

from dataclasses import fields

from .models import PeriodontistRecord


class Deduplicator:
    def merge(self, records: list[PeriodontistRecord]) -> list[PeriodontistRecord]:
        merged: dict[str, PeriodontistRecord] = {}
        for record in records:
            key = record.identity_key()
            if key not in merged:
                merged[key] = record
                continue
            merged[key] = self._prefer(merged[key], record)
        for record in merged.values():
            record.ensure_provider_id()
        return list(merged.values())

    @staticmethod
    def _prefer(left: PeriodontistRecord, right: PeriodontistRecord) -> PeriodontistRecord:
        winner, other = (left, right) if left.completeness_score() >= right.completeness_score() else (right, left)
        values = {}
        for item in fields(PeriodontistRecord):
            current = getattr(winner, item.name)
            fallback = getattr(other, item.name)
            if item.name == "provider_id":
                values[item.name] = current or fallback
            else:
                values[item.name] = current or fallback
        combined = PeriodontistRecord(**values)
        combined.ensure_provider_id()
        return combined
