"""One-time/idempotent import of runtime JSON records into MongoDB Atlas.

Usage:
    python scripts/migrate_json_to_mongodb.py --dry-run
    python scripts/migrate_json_to_mongodb.py

The destination must already be configured in .env with STORAGE_BACKEND=mongodb,
MONGODB_URI, and MONGODB_DATABASE. JSON files are read but never deleted. Re-running
is safe: each MongoDB document uses the old filename stem as its _id and is replaced
atomically by an upsert.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MIGRATABLE_COLLECTIONS = {
    "users",
    "parsed_resumes",
    "role_profiles",
    "analyses",
    "job_source_cache",
    "discovery_runs",
    "api_quota",
}


def _documents(source: Path):
    for collection in sorted(MIGRATABLE_COLLECTIONS):
        directory = source / collection
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError(f"Expected an object in {path}")
            yield collection, path.stem, document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data"),
        help="Legacy JSON data directory (default: ./data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and count documents without connecting to MongoDB",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_dir():
        parser.error(f"Source directory does not exist: {source}")

    counts: dict[str, int] = {}
    for collection, _key, _document in _documents(source):
        counts[collection] = counts.get(collection, 0) + 1

    if not counts:
        print(f"No migratable documents found under {source}")
        return

    print(f"Source: {source}")
    for collection, count in counts.items():
        print(f"  {collection:20} {count:6} document(s)")
    print(f"  {'TOTAL':20} {sum(counts.values()):6} document(s)")

    if args.dry_run:
        print("Dry run complete. No MongoDB connection was opened.")
        return

    # Imported only for a real migration so --dry-run remains useful on a
    # machine that has not configured Atlas yet.
    from app.config import settings
    from app.database import ensure_indexes
    from app.store import save_json

    if settings.storage_backend != "mongodb":
        parser.error(
            "Set STORAGE_BACKEND=mongodb and a valid MONGODB_URI in .env before importing"
        )

    ensure_indexes()
    imported = 0
    for collection, key, document in _documents(source):
        save_json(collection, key, document)
        imported += 1

    print(
        f"Imported {imported} document(s) into MongoDB database "
        f"{settings.mongodb_database!r}. JSON files were left unchanged."
    )


if __name__ == "__main__":
    main()
