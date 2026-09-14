from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web.app import app


def test_home_renders():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Periodontist Directory Scraper" in response.data
    assert b"Run scrape" in response.data


def test_registries_api():
    client = app.test_client()
    response = client.get("/api/registries?dental=1")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["count"] > 0
    assert "npi" in payload["implemented_api"]


def test_demo_scrape_and_csv_download():
    client = app.test_client()
    response = client.post("/api/scrape", json={"demo": True, "limit": 5, "registry": "npi"})
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["count"] == 2
    assert payload["records"][0]["name"]
    csv_response = client.get("/download/csv")
    assert csv_response.status_code == 200
    assert csv_response.mimetype.startswith("text/csv")
    assert b"provider_id" in csv_response.data
