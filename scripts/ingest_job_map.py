"""Refresh CareerStack's MongoDB-backed job map from approved sources.

Run this from an external scheduler (for example, Vercel Cron, GitHub Actions,
or Windows Task Scheduler). The web app only reads the resulting snapshot; it
never calls providers while serving map requests.

Examples:
    python scripts/ingest_job_map.py --dry-run
    python scripts/ingest_job_map.py
    python scripts/ingest_job_map.py --max-postings 500
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import close_database, initialize_database
from app.services.job_map import DEFAULT_INGEST_LIMIT, ingest_targets

DEFAULT_TARGETS = Path(__file__).resolve().parent.parent / "app" / "data" / "job_map_targets.json"


def _load_targets(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    targets = payload.get("targets")
    if not isinstance(targets, list):
        raise ValueError("The target config must contain a 'targets' list")
    return [target for target in targets if isinstance(target, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--max-postings", type=int, default=DEFAULT_INGEST_LIMIT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = _load_targets(args.targets)
    enabled = [target for target in targets if target.get("enabled", True)]
    print(f"Configured targets: {len(enabled)} enabled / {len(targets)} total")
    for target in enabled:
        print(f"  - {target.get('role')} · {target.get('location')}")

    if args.dry_run:
        print("Dry run complete. No provider or MongoDB call was made.")
        return
    if settings.storage_backend != "mongodb":
        parser.error("Set STORAGE_BACKEND=mongodb and MONGODB_URI before ingestion")
    if settings.demo_mode:
        parser.error("Refusing live ingestion while DEMO_MODE=true")

    async def run() -> dict:
        initialize_database()
        return await ingest_targets(targets, max_postings=args.max_postings)

    try:
        result = asyncio.run(run())
        print(json.dumps(result, indent=2))
    finally:
        close_database()


if __name__ == "__main__":
    main()
