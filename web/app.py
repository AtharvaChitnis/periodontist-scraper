from __future__ import annotations

from io import BytesIO
from pathlib import Path
from threading import Lock

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

from periodontist_scraper.jobs import run_scrape_job
from periodontist_scraper.models import SCHEMA_FIELDS
from periodontist_scraper.npi import US_STATES
from periodontist_scraper.registry_catalog import REGISTRIES, dental_registries, implemented_api_registries, scrapeable_registries

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

app = Flask(
    __name__,
    template_folder=str(WEB_DIR / "templates"),
    static_folder=str(WEB_DIR / "static"),
    static_url_path="/static",
)
app.json.sort_keys = False

_job_lock = Lock()
_last_job: dict = {
    "count": 0,
    "registry": "",
    "records": [],
    "outputs": {},
    "error": None,
    "filters": {},
    "stats": {},
}


def create_app() -> Flask:
    return app


@app.get("/")
def index():
    return render_template(
        "index.html",
        states=US_STATES,
        columns=SCHEMA_FIELDS,
        registries=dental_registries(),
        scrapeable=scrapeable_registries(True),
        implemented=[item["id"] for item in implemented_api_registries()],
        pipeline_steps=[
            "Search API",
            "URL Discovery",
            "Page Downloader (requests)",
            "HTML Parser (BeautifulSoup)",
            "Information Extraction",
            "Validation",
            "Deduplication",
            "pandas DataFrame",
            "CSV file",
        ],
    )


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/registries")
def api_registries():
    dental = request.args.get("dental") == "1"
    rows = dental_registries() if dental else REGISTRIES
    return jsonify(
        {
            "count": len(rows),
            "implemented_api": [item["id"] for item in implemented_api_registries()],
            "registries": rows,
        }
    )


@app.get("/api/results")
def api_results():
    return jsonify(_public_job())


@app.post("/api/scrape")
def api_scrape():
    payload = request.get_json(silent=True) or request.form.to_dict()
    options = {
        "registry": payload.get("registry") or "web_search",
        "state": payload.get("state") or "",
        "city": payload.get("city") or "",
        "last_name": payload.get("last_name") or "",
        "first_name": payload.get("first_name") or "",
        "query": payload.get("query") or payload.get("last_name") or "",
        "limit": payload.get("limit") or 10,
        "demo": _as_bool(payload.get("demo")),
        "all_states": _as_bool(payload.get("all_states")),
    }
    try:
        result = run_scrape_job(options)
        with _job_lock:
            _last_job.update(result)
            _last_job["error"] = None
        return jsonify(_public_job())
    except Exception as exc:
        with _job_lock:
            _last_job["error"] = str(exc)
        return jsonify({"error": str(exc), "count": 0, "records": []}), 400


@app.get("/download/<fmt>")
def download(fmt: str):
    records = _last_job.get("records") or []
    if not records:
        return jsonify({"error": "No results to download. Run a scrape first."}), 400
    frame = pd.DataFrame(records, columns=SCHEMA_FIELDS).fillna("")
    fmt = fmt.lower()
    if fmt == "csv":
        buffer = BytesIO()
        frame.to_csv(buffer, index=False)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="periodontists.csv", mimetype="text/csv")
    if fmt in {"xlsx", "excel"}:
        buffer = BytesIO()
        frame.to_excel(buffer, index=False)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name="periodontists.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return jsonify({"error": "Unsupported format. Use csv or xlsx."}), 400


def _public_job() -> dict:
    return {
        "count": _last_job.get("count") or 0,
        "registry": _last_job.get("registry") or "",
        "records": _last_job.get("records") or [],
        "outputs": _last_job.get("outputs") or {},
        "error": _last_job.get("error"),
        "filters": _last_job.get("filters") or {},
        "stats": _last_job.get("stats") or {},
        "columns": SCHEMA_FIELDS,
    }


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
