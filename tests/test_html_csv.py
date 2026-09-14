from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from periodontist_scraper.downloader import PageDownloader
from periodontist_scraper.models import SCHEMA_FIELDS, PageDocument
from periodontist_scraper.pipeline import ScrapePipeline
from periodontist_scraper.search import SearchAPI


def test_html_pipeline_extracts_fields_and_writes_csv(tmp_path, monkeypatch):
    html = (ROOT / "sample_pages" / "dr_maya_chen.html").read_text(encoding="utf-8")

    def fake_search(self, query=None):
        return [{"title": "Dr. Maya Chen Periodontist", "url": "https://lakesideperio.example/maya"}]

    def fake_fetch(self, url):
        return PageDocument(url=url, status_code=200, html=html)

    monkeypatch.setattr(SearchAPI, "search", fake_search)
    monkeypatch.setattr(PageDownloader, "fetch", fake_fetch)

    csv_path = tmp_path / "periodontists.csv"
    pipeline = ScrapePipeline(
        {
            "registry": "npi",
            "query": "periodontist",
            "max_pages": 5,
            "max_results": 5,
            "allowed_url_keywords": ["periodont", "perio"],
            "output": {"csv": str(csv_path)},
        }
    )
    records = pipeline.run("periodontist San Francisco")
    written = pipeline.export(records)
    assert pipeline.stats["pages_downloaded"] >= 1
    assert pipeline.stats["html_extracted"] >= 1
    assert any("Maya Chen" in rec.name for rec in records)
    record = records[0]
    assert record.name == "Dr. Maya Chen"
    assert record.first_name == "Maya"
    assert record.last_name == "Chen"
    assert record.phone == "(415) 555-0148"
    assert record.email == "maya.chen@lakesideperio.example"
    assert record.specialty == "Periodontics"
    assert record.city == "San Francisco"
    assert Path(written["csv"]).exists()
    with Path(written["csv"]).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0].keys()) == SCHEMA_FIELDS
    assert rows[0]["name"] == "Dr. Maya Chen"
    assert rows[0]["registration_number"]


def test_demo_html_job_writes_required_csv_columns(tmp_path, monkeypatch):
    from periodontist_scraper.jobs import run_scrape_job

    monkeypatch.setattr(
        "periodontist_scraper.jobs.load_config",
        lambda path=None: {"output": {"csv": str(tmp_path / "out.csv")}},
    )
    result = run_scrape_job({"demo": True, "limit": 5})
    assert result["count"] == 2
    path = Path(result["outputs"]["csv"])
    assert path.exists()
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0].keys()) == SCHEMA_FIELDS
    names = {row["name"] for row in rows}
    assert any("Maya Chen" in name for name in names)
    assert any("Luis Romero" in name for name in names)
