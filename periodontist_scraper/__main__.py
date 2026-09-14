from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .pipeline import ScrapePipeline
from .registry_catalog import REGISTRIES, dental_registries, implemented_api_registries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download periodontist HTML pages, extract directory fields with BeautifulSoup, "
            "and write CSV."
        )
    )
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config")
    parser.add_argument("--query", help="Optional name filter passed to the registry search")
    parser.add_argument("--registry", default="", help="Registry id (default: web_search HTML crawl)")
    parser.add_argument("--state", default="", help="U.S. state code for NPI search, e.g. CA")
    parser.add_argument("--city", default="", help="City filter for NPI search")
    parser.add_argument("--all-states", action="store_true", help="Page NPI results across all U.S. states")
    parser.add_argument("--demo", action="store_true", help="Run against bundled sample HTML instead of the internet")
    parser.add_argument("--limit", type=int, help="Max records/pages to collect")
    parser.add_argument("--list-registries", action="store_true", help="Print the public registry catalog and exit")
    parser.add_argument("--dental-only", action="store_true", help="With --list-registries, show dental-relevant sources only")
    parser.add_argument("--web", action="store_true", help="Start the web UI on http://127.0.0.1:5050")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.web:
        from web.app import main as run_web

        run_web()
        return 0

    if args.list_registries:
        rows = dental_registries() if args.dental_only else REGISTRIES
        payload = {
            "count": len(rows),
            "implemented_api": [item["id"] for item in implemented_api_registries()],
            "registries": rows,
        }
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    config = load_config(args.config)
    if args.limit:
        config["max_pages"] = args.limit
        config["max_results"] = args.limit
    if args.registry:
        config["registry"] = args.registry
        config["source_registry"] = args.registry
    if args.state:
        config["state"] = args.state
    if args.city:
        config["city"] = args.city
    if args.all_states:
        config["all_states"] = True
    if args.demo:
        config["source_registry"] = "sample_pages"
        config["registry"] = "sample_pages"
    config.setdefault("registry", "web_search")
    pipeline = ScrapePipeline(config)
    if args.demo:
        sample_dir = Path(__file__).resolve().parent.parent / "sample_pages"
        html_files = sorted(sample_dir.glob("*.html"))
        records = pipeline.run_local(html_files)
    else:
        records = pipeline.run(args.query)
    written = pipeline.export(records)
    payload = {
        "count": len(records),
        "registry": config.get("registry") or "web_search",
        "records": [record.as_dict() for record in records],
        "outputs": written,
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
