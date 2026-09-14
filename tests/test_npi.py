import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from periodontist_scraper.npi import NPIRegistryClient
from periodontist_scraper.pipeline import ScrapePipeline
from periodontist_scraper.registry_catalog import dental_registries, get_registry, implemented_api_registries
from periodontist_scraper.validate import RecordValidator


def test_npi_maps_official_api_payload():
    payload = json.loads((ROOT / "tests" / "fixtures" / "npi_sample.json").read_text(encoding="utf-8"))
    client = NPIRegistryClient({"source_registry": "npi"})
    first = client.map_result(payload["results"][0])
    assert first is not None
    assert first.provider_id == "1780658039"
    assert first.registration_number == "1780658039"
    assert first.first_name == "Alexandre"
    assert first.last_name == "Aalam"
    assert first.specialty == "Periodontics"
    assert first.city == "Phoenix"
    assert first.state == "AZ"
    assert first.country == "United States"
    assert first.phone == "(602) 867-7700"
    assert first.qualification == "DDS"
    assert first.registration_year == "2006"
    assert first.source_registry == "NPPES NPI Registry"
    assert "1780658039" in first.source_url
    assert RecordValidator().is_valid(first)


def test_pipeline_scrapes_html_pages(monkeypatch, tmp_path):
    html = (ROOT / "sample_pages" / "dr_maya_chen.html").read_text(encoding="utf-8")

    def fake_search(self, query=None):
        return [{"title": "Maya Chen Periodontist", "url": "https://lakesideperio.example/maya"}]

    def fake_fetch(self, url):
        from periodontist_scraper.models import PageDocument

        return PageDocument(url=url, status_code=200, html=html)

    monkeypatch.setattr("periodontist_scraper.search.SearchAPI.search", fake_search)
    monkeypatch.setattr("periodontist_scraper.downloader.PageDownloader.fetch", fake_fetch)
    pipeline = ScrapePipeline(
        {
            "registry": "npi",
            "allowed_url_keywords": ["periodont", "perio"],
            "max_pages": 3,
            "output": {"csv": str(tmp_path / "npi.csv")},
        }
    )
    records = pipeline.run()
    written = pipeline.export(records)
    assert any(row.email == "maya.chen@lakesideperio.example" for row in records)
    assert Path(written["csv"]).exists()


def test_catalog_includes_npi_and_dental_boards():
    npi = get_registry("npi")
    assert npi is not None
    assert npi["official_url"].startswith("https://npiregistry.cms.hhs.gov")
    assert "npi" in {item["id"] for item in implemented_api_registries()}
    dental_ids = {item["id"] for item in dental_registries()}
    assert "uk_gdc" in dental_ids
    assert "au_dental_board" in dental_ids
    assert "nz_dental" in dental_ids
    gdc = get_registry("uk_gdc")
    assert gdc["webpage"].startswith("https://www.gdc-uk.org")
