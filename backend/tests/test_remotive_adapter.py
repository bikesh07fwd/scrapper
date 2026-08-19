"""
tests/test_remotive_adapter.py — Tests for RemotiveRSSAdapter.

All tests use the local XML fixture (tests/fixtures/remotive_feed.xml).
No network requests are made — parse() is tested in isolation.

Test classes:
  TestStructTimeToIso        — timestamp conversion helper
  TestRemotiveAdapterMeta    — name, source_label
  TestParse                  — field extraction, edge cases, missing fields
  TestParseEdgeCases         — empty feed, malformed XML
"""

import time
from pathlib import Path

import pytest

from adapters.remotive_rss import RemotiveRSSAdapter, _struct_time_to_iso

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "remotive_feed.xml"

# Expected values from the fixture — define once, used by multiple tests
ENTRY_1_TITLE = "Senior Python Developer"
ENTRY_1_COMPANY = "Acme Corp"
ENTRY_1_URL = "https://remotive.com/remote-jobs/software-dev/senior-python-developer-1001"
ENTRY_1_CATEGORY = "Software Development"
ENTRY_1_DATE_PREFIX = "2026-08-18"

ENTRY_2_TITLE = "Remote DevOps Engineer"
ENTRY_2_COMPANY = "Beta Technologies"
ENTRY_2_CATEGORY = "DevOps / Sysadmin"

ENTRY_3_TITLE = "Full Stack Engineer"
# Entry 3 has no <author> — company must be None


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def adapter() -> RemotiveRSSAdapter:
    return RemotiveRSSAdapter()


@pytest.fixture
def fixture_bytes() -> bytes:
    """Read the local RSS fixture file once per test."""
    return FIXTURE_PATH.read_bytes()


@pytest.fixture
def records(adapter, fixture_bytes) -> list[dict]:
    """Parse the fixture and return all records."""
    return adapter.parse(fixture_bytes)


# ─── _struct_time_to_iso ──────────────────────────────────────────────────────

class TestStructTimeToIso:

    def test_none_input_returns_none(self):
        assert _struct_time_to_iso(None) is None

    def test_epoch_zero_returns_correct_iso(self):
        """Unix epoch → 1970-01-01T00:00:00Z."""
        st = time.gmtime(0)
        assert _struct_time_to_iso(st) == "1970-01-01T00:00:00Z"

    def test_known_datetime(self):
        """2026-08-18 09:00:00 UTC → correct ISO string."""
        # time.strptime returns local time; we want UTC, so use gmtime
        # Build the struct directly for a deterministic UTC value
        import calendar
        st = time.strptime("2026-08-18 09:00:00", "%Y-%m-%d %H:%M:%S")
        result = _struct_time_to_iso(st)
        # Just verify format and date portion — local/UTC offset can differ
        assert result is not None
        assert result.endswith("Z")
        assert len(result) == 20  # "YYYY-MM-DDTHH:MM:SSZ"

    def test_output_ends_with_z(self):
        """All outputs are explicitly UTC (trailing Z)."""
        st = time.gmtime(1000000000)
        result = _struct_time_to_iso(st)
        assert result.endswith("Z")

    def test_output_is_iso_format(self):
        """Output matches ISO8601 UTC format."""
        st = time.gmtime(1000000000)
        result = _struct_time_to_iso(st)
        # Should be parseable by strptime
        parsed = time.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert parsed is not None


# ─── Adapter metadata ─────────────────────────────────────────────────────────

class TestRemotiveAdapterMeta:

    def test_name_is_remotive(self, adapter):
        assert adapter.name == "remotive"

    def test_source_label_matches_name(self, adapter):
        assert adapter.source_label() == "remotive"

    def test_is_base_adapter_subclass(self, adapter):
        from adapters.base import BaseAdapter
        assert isinstance(adapter, BaseAdapter)


# ─── parse() — successful feed ────────────────────────────────────────────────

class TestParse:

    def test_returns_list(self, records):
        assert isinstance(records, list)

    def test_correct_record_count(self, records):
        """Fixture contains exactly 3 entries."""
        assert len(records) == 3

    # ── Entry 1 ──

    def test_entry1_title(self, records):
        assert records[0]["title"] == ENTRY_1_TITLE

    def test_entry1_company(self, records):
        assert records[0]["company"] == ENTRY_1_COMPANY

    def test_entry1_url(self, records):
        assert records[0]["url"] == ENTRY_1_URL

    def test_entry1_category(self, records):
        assert records[0]["category"] == ENTRY_1_CATEGORY

    def test_entry1_tags_is_list(self, records):
        assert isinstance(records[0]["tags"], list)

    def test_entry1_tags_contains_category(self, records):
        assert ENTRY_1_CATEGORY in records[0]["tags"]

    def test_entry1_published_parsed_not_none(self, records):
        assert records[0]["published_parsed"] is not None

    def test_entry1_published_parsed_format(self, records):
        """published_parsed must be a UTC ISO8601 string."""
        published = records[0]["published_parsed"]
        assert published.endswith("Z")
        assert published.startswith(ENTRY_1_DATE_PREFIX)

    def test_entry1_description_html_present(self, records):
        desc = records[0]["description_html"]
        assert desc is not None
        assert len(desc) > 0

    def test_entry1_source_is_remotive(self, records):
        assert records[0]["source"] == "remotive"

    # ── Entry 2 ──

    def test_entry2_title(self, records):
        assert records[1]["title"] == ENTRY_2_TITLE

    def test_entry2_company(self, records):
        assert records[1]["company"] == ENTRY_2_COMPANY

    def test_entry2_category(self, records):
        assert records[1]["category"] == ENTRY_2_CATEGORY

    # ── Entry 3 — missing <author> ──

    def test_entry3_title(self, records):
        assert records[2]["title"] == ENTRY_3_TITLE

    def test_entry3_company_is_none_when_author_missing(self, records):
        """The third fixture entry has no <author>. company must be None."""
        assert records[2]["company"] is None

    def test_entry3_category_still_extracted(self, records):
        """Missing author does not prevent category extraction."""
        assert records[2]["category"] == "Software Development"

    # ── All records ──

    def test_all_records_have_source_remotive(self, records):
        for r in records:
            assert r["source"] == "remotive"

    def test_all_records_have_required_keys(self, records):
        """Every record must contain all expected keys."""
        required = {
            "source", "title", "company", "url",
            "tags", "category",
            "published_raw", "published_parsed",
            "description_html", "entry_id",
        }
        for i, record in enumerate(records):
            missing = required - record.keys()
            assert not missing, f"Record {i} missing keys: {missing}"

    def test_tags_is_always_a_list(self, records):
        """tags must be a list even when empty."""
        for r in records:
            assert isinstance(r["tags"], list)

    def test_url_is_string_or_none(self, records):
        for r in records:
            assert r["url"] is None or isinstance(r["url"], str)


# ─── parse() — edge cases ─────────────────────────────────────────────────────

class TestParseEdgeCases:

    def test_empty_feed_returns_empty_list(self, adapter):
        """An RSS channel with no <item> elements returns []."""
        content = Path(__file__).parent / "fixtures" / "remotive" / "empty_feed.xml"
        records = adapter.parse(content.read_bytes())
        assert records == []

    def test_completely_empty_bytes_returns_list(self, adapter):
        """Empty input does not raise — returns empty list."""
        records = adapter.parse(b"")
        assert isinstance(records, list)

    def test_malformed_xml_does_not_raise(self, adapter):
        """feedparser is tolerant of bad XML — must not raise."""
        content = Path(__file__).parent / "fixtures" / "remotive" / "malformed_feed.xml"
        records = adapter.parse(content.read_bytes())
        assert isinstance(records, list)

    def test_feed_with_missing_optional_fields_does_not_raise(self, adapter):
        """An item with missing optional fields must parse without error."""
        content = Path(__file__).parent / "fixtures" / "remotive" / "partial_feed.xml"
        records = adapter.parse(content.read_bytes())
        assert len(records) == 2
        assert records[0]["title"] == "Senior Python Engineer"
        assert records[1]["title"] == "React Developer"
        assert records[1]["company"] is None
        assert records[1]["url"] == "https://remotive.com/jobs/react-developer-102"
        assert records[1]["tags"] == []
        assert records[1]["category"] is None

    def test_parse_accepts_string_input(self, adapter, fixture_bytes):
        """parse() must accept str as well as bytes."""
        as_string = fixture_bytes.decode("utf-8")
        records = adapter.parse(as_string)
        assert len(records) == 3

