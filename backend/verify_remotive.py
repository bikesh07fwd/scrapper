"""
verify_remotive.py — Standalone verification script for Phase 2.

Runs RemotiveRSSAdapter against the real Remotive RSS feed and prints
a summary. Does NOT write to a database or interact with any other
pipeline stage.

Usage (from backend/):
    python verify_remotive.py

Expected output:
    Source      : remotive
    URL         : https://remotive.com/remote-jobs/feed
    Status      : fetching...
    Jobs fetched: 127

    First job:
      Title    : Senior Backend Engineer
      Company  : Acme Corp
      URL      : https://remotive.com/remote-jobs/...
      Category : Software Development
      Tags     : ['Software Development']
      Published: 2026-08-18T07:00:00Z
"""

import asyncio
import os

# Set a placeholder DATABASE_URL so config.py can be imported.
# This script does not use the database.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://placeholder/placeholder",
)

from adapters.remotive_rss import RemotiveRSSAdapter  # noqa: E402
from pipeline.fetcher import FetchError  # noqa: E402


async def main() -> None:
    adapter = RemotiveRSSAdapter()

    print(f"\nSource : {adapter.source_label()}")
    print(f"URL    : https://remotive.com/remote-jobs/feed")
    print("Status : fetching...\n")

    try:
        raw = await adapter.fetch()
    except FetchError as exc:
        print(f"ERROR: {exc}")
        return

    records = adapter.parse(raw)
    print(f"Jobs fetched: {len(records)}")

    if not records:
        print("No jobs returned — the feed may be empty or temporarily unavailable.")
        return

    first = records[0]
    print("\nFirst job:")
    print(f"  Title    : {first.get('title') or 'N/A'}")
    print(f"  Company  : {first.get('company') or 'N/A'}")
    print(f"  URL      : {first.get('url') or 'N/A'}")
    print(f"  Category : {first.get('category') or 'N/A'}")
    print(f"  Tags     : {first.get('tags', [])}")
    print(f"  Published: {first.get('published_parsed') or 'N/A'}")

    if len(records) > 1:
        print(f"\n  ... and {len(records) - 1} more job(s)")


if __name__ == "__main__":
    asyncio.run(main())
