from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from periodontist_scraper.dedupe import Deduplicator
from periodontist_scraper.discovery import URLDiscovery
from periodontist_scraper.export import DataExporter
from periodontist_scraper.extract import InformationExtractor
from periodontist_scraper.models import SCHEMA_FIELDS, PageDocument, PeriodontistRecord
from periodontist_scraper.pipeline import ScrapePipeline
from periodontist_scraper.validate import RecordValidator


def test_extracts_jsonld_person():
    html = (ROOT / "sample_pages" / "dr_maya_chen.html").read_text(encoding="utf-8")
    page = PageDocument(url="https://lakesideperio.example/maya", status_code=200, html=html)
    records = InformationExtractor({"source_registry": "web_search"}).extract(page)
    assert len(records) == 1
    record = records[0]
    assert record.name == "Dr. Maya Chen"
    assert record.first_name == "Maya"
    assert record.last_name == "Chen"
    assert record.phone == "(415) 555-0148"
    assert record.email == "maya.chen@lakesideperio.example"
    assert "Periodontist" in record.job_title
    assert record.specialty == "Periodontics"
    assert record.clinic_name == "Lakeside Periodontics"
    assert record.city == "San Francisco"
    assert record.state == "CA"
    assert record.country == "United States"
    assert record.qualification
    assert "CA-PERIO-4418" in record.registration_number
    assert record.registration_year == "2009"
    assert record.experience_years == "15"
    assert record.provider_id
    assert record.source_url.endswith("/maya")
    assert record.last_verified


def test_extracts_heuristic_fields():
    html = (ROOT / "sample_pages" / "dr_luis_romero.html").read_text(encoding="utf-8")
    page = PageDocument(url="https://northsideperio.example/luis", status_code=200, html=html)
    record = InformationExtractor().extract(page)[0]
    assert "Luis Romero" in record.name
    assert record.first_name == "Luis"
    assert record.last_name == "Romero"
    assert record.phone == "(212) 555-0199"
    assert record.email == "office@northsideperio.example"
    assert record.job_title
    assert record.experience_years == "22"
    assert record.clinic_name == "Northside Periodontics"
    assert record.hospital == "Lenox Hill Hospital"
    assert record.city == "New York"
    assert record.state == "NY"
    assert record.registration_number == "NY-88210"
    assert record.registration_year == "2001"
    assert "implant" in record.subspecialty.lower()


def test_validator_rejects_empty_and_bad_email():
    validator = RecordValidator()
    assert not validator.is_valid(PeriodontistRecord())
    assert not validator.is_valid(PeriodontistRecord(name="Dr. Test", email="not-an-email"))
    assert validator.is_valid(
        PeriodontistRecord(name="Dr. Test", email="test@clinic.example", phone="(212) 555-0199")
    )


def test_dedupe_merges_same_email():
    left = PeriodontistRecord(name="Maya Chen", email="maya.chen@lakesideperio.example", phone="")
    right = PeriodontistRecord(
        name="Dr. Maya Chen",
        email="maya.chen@lakesideperio.example",
        phone="(415) 555-0148",
        city="San Francisco",
    )
    merged = Deduplicator().merge([left, right])
    assert len(merged) == 1
    assert merged[0].phone == "(415) 555-0148"
    assert merged[0].city == "San Francisco"


def test_url_discovery_filters_blocked_and_unrelated():
    discovery = URLDiscovery(
        {
            "allowed_url_keywords": ["periodont", "dental"],
            "blocked_url_keywords": ["facebook.com"],
            "max_pages": 10,
        }
    )
    urls = discovery.discover(
        [
            {"title": "Periodontist in Austin", "url": "https://austinperio.example/doctors"},
            {"title": "Clinic Facebook", "url": "https://facebook.com/austinperio"},
            {"title": "Random blog", "url": "https://example.com/cats"},
        ]
    )
    assert urls == ["https://austinperio.example/doctors"]


def test_demo_pipeline(tmp_path):
    config = {
        "source_registry": "sample_pages",
        "output": {
            "csv": str(tmp_path / "out.csv"),
            "excel": str(tmp_path / "out.xlsx"),
            "sqlite": str(tmp_path / "out.db"),
        },
    }
    pipeline = ScrapePipeline(config)
    records = pipeline.run_local((ROOT / "sample_pages").glob("*.html"))
    written = pipeline.export(records)
    assert len(records) == 2
    frame = DataExporter().to_dataframe(records)
    assert list(frame.columns) == SCHEMA_FIELDS
    assert Path(written["csv"]).exists()
    assert Path(written["excel"]).exists()
    assert Path(written["sqlite"]).exists()
    with sqlite3.connect(written["sqlite"]) as connection:
        rows = connection.execute("select count(*) from periodontists").fetchone()
    assert rows[0] == 2
