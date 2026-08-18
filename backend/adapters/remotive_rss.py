"""
adapters/remotive_rss.py — Adapter for the Remotive public RSS feed.

Source:  https://remotive.com/remote-jobs/feed
Format:  RSS 2.0 over HTTPS
Auth:    None — Remotive explicitly provides this feed for third-party use
Terms:   We use this source because Remotive explicitly provides a public
         feed for programmatic access under their published terms.

What this adapter does:
  1. fetch()  — GET the RSS feed URL via the shared fetcher
  2. parse()  — convert feedparser entries into raw record dicts

What this adapter does NOT do:
  - Validate or normalize field values (Phase 3)
  - Write to the database (Phase 3)
  - Deduplicate (Phase 3)
  - Handle circuit state (Phase 4)

Fixture-based testing:
  parse() accepts raw bytes directly, so tests can pass a local XML
  fixture file instead of hitting the network.
"""

import calendar
import time
from typing import Optional, Union

import feedparser
import structlog

from adapters.base import BaseAdapter
from pipeline.fetcher import fetch as http_fetch

logger = structlog.get_logger(__name__)

# Public RSS feed URL — no authentication required
RSS_URL = "https://remotive.com/remote-jobs/feed"


class RemotiveRSSAdapter(BaseAdapter):
    """
    Adapter for the Remotive public RSS feed.

    Returns raw record dicts with these keys:
        source           — always "remotive"
        title            — job title string, or None
        company          — hiring company name (from RSS <author>), or None
        url              — direct link to the job listing, or None
        tags             — list of tag strings (may be empty)
        category         — first tag string, or None (Remotive uses tags as categories)
        published_raw    — original date string from the feed, or None
        published_parsed — UTC ISO8601 string (e.g. "2026-08-18T09:00:00Z"), or None
        description_html — raw HTML description, or None (will be stripped in Phase 3)
        entry_id         — feedparser entry ID, used for reference; not the dedup key
    """

    name = "remotive"

    async def fetch(self) -> bytes:
        """
        Fetch the Remotive RSS feed.

        Delegates all retry, backoff, and timeout logic to the shared fetcher.
        Returns raw RSS bytes.

        Note on ETag / conditional GET:
          The fetcher supports an `extra_headers` parameter for passing
          If-None-Match / If-Modified-Since. This is left as a future
          enhancement once the persister (Phase 3) can store the ETag
          from a previous response.
        """
        return await http_fetch(RSS_URL)

    def parse(self, raw: Union[str, bytes]) -> list[dict]:
        """
        Parse raw RSS bytes into a list of raw record dicts.

        feedparser is resilient — it returns partial results even for
        malformed feeds and signals problems via feed.bozo. We log bozo
        warnings but continue if there are entries to process.

        Individual entry errors are logged and skipped, never raised,
        so one bad record does not abort the rest of the batch.

        Args:
            raw: Bytes or string returned by fetch() or read from a fixture file.

        Returns:
            List of raw dicts, one per job entry. May be empty.
        """
        feed = feedparser.parse(raw)

        if feed.bozo:
            # bozo=True means feedparser encountered a parse problem.
            # The feed may still contain usable entries, so we continue.
            logger.warning(
                "remotive.parse.bozo",
                exception=str(getattr(feed, "bozo_exception", "unknown")),
                entry_count=len(feed.entries),
            )

        if not feed.entries:
            logger.info("remotive.parse.empty_feed")
            return []

        records: list[dict] = []
        for i, entry in enumerate(feed.entries):
            try:
                record = self._entry_to_dict(entry)
                records.append(record)
            except Exception as exc:
                # One entry failing should not abort the entire batch.
                logger.warning(
                    "remotive.parse.entry_error",
                    entry_index=i,
                    error=str(exc),
                )

        logger.info("remotive.parse.complete", total=len(records))
        return records

    def _entry_to_dict(self, entry: feedparser.FeedParserDict) -> dict:
        """
        Map a single feedparser entry to a raw record dict.

        All fields are optional — missing source fields become None or [].
        Type coercion and default-filling are the normalizer's job (Phase 3).

        feedparser field notes:
          entry.author  — Remotive puts the company name here
          entry.tags    — list of tag objects; each has a .term attribute
          entry.published_parsed — time.struct_time in UTC (feedparser normalises this)
          entry.summary — HTML description body
        """
        tags: list[str] = [
            t.term for t in entry.get("tags", []) if hasattr(t, "term") and t.term
        ]

        return {
            "source": self.name,
            # Core fields
            "title": entry.get("title") or None,
            "company": entry.get("author") or None,
            "url": entry.get("link") or None,
            # Tags and category
            "tags": tags,
            "category": tags[0] if tags else None,
            # Timestamps — both forms kept; normaliser decides which to use
            "published_raw": entry.get("published") or None,
            "published_parsed": _struct_time_to_iso(entry.get("published_parsed")),
            # HTML description — will be stripped by the normaliser
            "description_html": entry.get("summary") or None,
            # feedparser's entry identifier (often equals the URL)
            "entry_id": entry.get("id") or entry.get("link") or None,
        }


# ─── Module-level helper ──────────────────────────────────────────────────────

def _struct_time_to_iso(st: Optional[time.struct_time]) -> Optional[str]:
    """
    Convert a feedparser published_parsed value to a UTC ISO8601 string.

    feedparser always normalises published_parsed to UTC, so
    calendar.timegm (which interprets the struct_time as UTC) is correct.
    time.mktime would be wrong here — it assumes local time.

    Args:
        st: A time.struct_time object, or None if the entry has no date.

    Returns:
        A string like "2026-08-18T09:00:00Z", or None.
    """
    if st is None:
        return None
    # calendar.timegm: UTC struct_time → UTC epoch seconds (no timezone offset)
    epoch_seconds = calendar.timegm(st)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))
