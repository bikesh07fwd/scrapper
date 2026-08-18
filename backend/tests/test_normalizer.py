"""
tests/test_normalizer.py — Tests for pipeline/normalizer.py.
"""

from datetime import datetime, timezone
import json
from pipeline.validator import RawJobRecord
from pipeline.normalizer import (
    normalize_record,
    strip_html_tags,
    normalize_location,
    normalize_published_at,
    compute_external_id,
)


class TestNormalizer:

    def test_strip_html_tags(self):
        """Must strip HTML tags, unescape entities, and normalize internal whitespace."""
        html_input = "  <p>Hello &amp; welcome to <b>Acdyon</b>!</p>   <br/>  Next line.  "
        expected = "Hello & welcome to Acdyon! Next line."
        assert strip_html_tags(html_input) == expected

    def test_normalize_location(self):
        """Must normalize Remote keywords consistently and preserve other locations."""
        assert normalize_location("anywhere") == "Remote"
        assert normalize_location("WORLDWIDE") == "Remote"
        assert normalize_location("  work from home  ") == "Remote"
        assert normalize_location(None) == "Remote"
        assert normalize_location("") == "Remote"
        assert normalize_location("New York, NY") == "New York, NY"
        assert normalize_location("London, UK") == "London, UK"

    def test_normalize_published_at_valid(self):
        """Must parse UTC timezone-aware ISO string correctly."""
        iso_str = "2026-08-18T09:30:00Z"
        dt = normalize_published_at(iso_str)
        assert dt.tzinfo == timezone.utc
        assert dt.year == 2026
        assert dt.month == 8
        assert dt.day == 18
        assert dt.hour == 9
        assert dt.minute == 30

    def test_normalize_published_at_timezone_aware(self):
        """Ensure timezone offset formats are normalized back to UTC."""
        iso_offset = "2026-08-18T09:30:00+02:00"
        dt = normalize_published_at(iso_offset)
        assert dt.tzinfo == timezone.utc
        # 09:30 +02:00 is 07:30 UTC
        assert dt.hour == 7
        assert dt.minute == 30

    def test_normalize_published_at_invalid_fallback(self):
        """Invalid timestamp must fall back to the current time in UTC."""
        dt = normalize_published_at("invalid timestamp format")
        assert dt.tzinfo == timezone.utc
        # Difference from now should be tiny (fractions of a second)
        diff = datetime.now(timezone.utc) - dt
        assert diff.total_seconds() < 5.0

    def test_normalize_published_at_missing_fallback(self):
        """Missing timestamp must fall back to current time in UTC."""
        dt = normalize_published_at(None)
        assert dt.tzinfo == timezone.utc
        diff = datetime.now(timezone.utc) - dt
        assert diff.total_seconds() < 5.0

    def test_description_truncation(self):
        """Must strip HTML and truncate to exactly 500 characters max."""
        long_desc = "Test " * 200  # 1000 characters
        raw = RawJobRecord(
            source="remotive",
            title="Dev",
            description_html=f"<div>{long_desc}</div>",
        )
        normalized = normalize_record(raw)
        desc_snippet = normalized["description_snippet"]
        assert len(desc_snippet) == 500
        assert not desc_snippet.startswith("<div>")
        assert desc_snippet.endswith("Test") or desc_snippet.endswith(" ")

    def test_company_fallback(self):
        """Must fall back to 'Unknown' if company is missing or empty."""
        raw_missing = RawJobRecord(source="remotive", title="Job A", company=None)
        raw_whitespace = RawJobRecord(source="remotive", title="Job B", company="   ")
        assert normalize_record(raw_missing)["company"] == "Unknown"
        assert normalize_record(raw_whitespace)["company"] == "Unknown"

    def test_tags_deduplication(self):
        """Must clean whitespace, remove duplicates, and serialize tags to JSON."""
        raw = RawJobRecord(
            source="remotive",
            title="Dev",
            tags=[" Python ", "python", "Django", "python"],
        )
        normalized = normalize_record(raw)
        # Should result in ["Python", "Django"]
        tags_list = json.loads(normalized["tags"])
        assert tags_list == ["Python", "Django"]

    def test_external_id_determinism(self):
        """Same source and URL must produce identical hashes."""
        url = "https://example.com/jobs/1"
        id1 = compute_external_id("remotive", url)
        id2 = compute_external_id("remotive", url)
        assert id1 == id2

    def test_different_source_different_external_id(self):
        """Different sources pointing to same URL must produce distinct hashes."""
        url = "https://example.com/jobs/1"
        id_remotive = compute_external_id("remotive", url)
        id_sandbox = compute_external_id("sandbox", url)
        assert id_remotive != id_sandbox
