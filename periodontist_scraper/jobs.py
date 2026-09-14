from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import load_config
from .pipeline import ScrapePipeline


ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample_pages"


def run_scrape_job(options: dict[str, Any], config_path: str | Path | None = None) -> dict[str, Any]:
    config = deepcopy(load_config(config_path))
    registry = (options.get("registry") or config.get("registry") or "web_search").strip().lower()
    demo = bool(options.get("demo"))
    limit = int(options.get("limit") or config.get("max_results") or 25)
    limit = max(1, min(limit, 200))
    config["max_results"] = limit
    config["max_pages"] = limit
    config["registry"] = registry
    config["source_registry"] = "sample_pages" if demo else registry
    config["state"] = (options.get("state") or "").strip().upper()
    config["city"] = (options.get("city") or "").strip()
    config["last_name"] = (options.get("last_name") or "").strip()
    config["first_name"] = (options.get("first_name") or "").strip()
    config["location"] = " ".join(part for part in (config["city"], config["state"]) if part)
    config["all_states"] = bool(options.get("all_states"))
    output = dict(config.get("output") or {})
    output.setdefault("csv", str(ROOT / "data" / "periodontists.csv"))
    config["output"] = output
    query = (options.get("query") or "").strip() or None

    pipeline = ScrapePipeline(config)
    if demo:
        records = pipeline.run_local(sorted(SAMPLE_DIR.glob("*.html")))
        registry = "sample_pages"
    else:
        records = pipeline.run(query)
    written = pipeline.export(records)
    return {
        "count": len(records),
        "registry": registry,
        "records": [record.as_dict() for record in records],
        "outputs": written,
        "stats": pipeline.stats,
        "filters": {
            "state": config.get("state") or "",
            "city": config.get("city") or "",
            "limit": limit,
            "demo": demo,
        },
    }
