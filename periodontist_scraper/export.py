"""Export pandas DataFrame to CSV, Excel, and SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from .models import SCHEMA_FIELDS, PeriodontistRecord


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS periodontists (
    provider_id TEXT PRIMARY KEY,
    name TEXT,
    first_name TEXT,
    last_name TEXT,
    profession TEXT,
    job_title TEXT,
    specialty TEXT,
    subspecialty TEXT,
    qualification TEXT,
    registration_number TEXT,
    registration_year TEXT,
    experience_years TEXT,
    clinic_name TEXT,
    hospital TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    source_registry TEXT,
    source_url TEXT,
    last_verified TEXT
)
"""


class DataExporter:
    def to_dataframe(self, records: list[PeriodontistRecord]) -> pd.DataFrame:
        rows = [record.as_dict() for record in records]
        frame = pd.DataFrame(rows, columns=SCHEMA_FIELDS)
        return frame.fillna("")

    def export(self, records: list[PeriodontistRecord], output: dict[str, Any]) -> dict[str, str]:
        frame = self.to_dataframe(records)
        written: dict[str, str] = {}
        csv_path = output.get("csv")
        excel_path = output.get("excel")
        sqlite_path = output.get("sqlite")
        if csv_path:
            path = Path(csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False)
            written["csv"] = str(path)
        if excel_path:
            path = Path(excel_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_excel(path, index=False)
            written["excel"] = str(path)
        if sqlite_path:
            path = Path(sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(path) as connection:
                connection.execute(CREATE_TABLE_SQL)
                frame.to_sql("periodontists", connection, if_exists="replace", index=False)
            written["sqlite"] = str(path)
        return written
