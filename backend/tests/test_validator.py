"""
tests/test_validator.py — Tests for pipeline/validator.py.
"""

import pytest
from pydantic import ValidationError
from pipeline.validator import RawJobRecord, validate_records


class TestValidator:

    def test_valid_record(self):
        """A complete valid raw record must validate successfully."""
        data = {
            "source": "remotive",
            "title": "Software Engineer",
            "company": "Acme Inc.",
            "url": "https://example.com/job1",
            "tags": ["python", "django"],
            "category": "Software",
            "published_raw": "Mon, 18 Aug 2026 09:00:00 +0000",
            "published_parsed": "2026-08-18T09:00:00Z",
            "description_html": "<p>A nice job</p>",
            "entry_id": "job123",
        }
        record = RawJobRecord.model_validate(data)
        assert record.source == "remotive"
        assert record.title == "Software Engineer"
        assert record.company == "Acme Inc."
        assert record.url == "https://example.com/job1"
        assert record.tags == ["python", "django"]

    def test_missing_title_but_url_present(self):
        """A record with no title but a valid URL must still be valid."""
        data = {
            "source": "remotive",
            "title": None,
            "url": "https://example.com/job1",
        }
        record = RawJobRecord.model_validate(data)
        assert record.title is None
        assert record.url == "https://example.com/job1"

    def test_missing_url_but_title_present(self):
        """A record with no URL but a valid title must still be valid."""
        data = {
            "source": "remotive",
            "title": "Data Scientist",
            "url": None,
        }
        record = RawJobRecord.model_validate(data)
        assert record.title == "Data Scientist"
        assert record.url is None

    def test_missing_title_and_url_raises_error(self):
        """A record missing both title and URL must raise a validation error."""
        data = {
            "source": "remotive",
            "title": None,
            "url": None,
        }
        with pytest.raises(ValidationError) as exc_info:
            RawJobRecord.model_validate(data)
        assert "must have at least a non-empty title or a non-empty url" in str(exc_info.value)

    def test_whitespace_only_title_and_url_treated_as_missing(self):
        """Whitespace-only fields are cleaned to None and raise validation error."""
        data = {
            "source": "remotive",
            "title": "   ",
            "url": "",
        }
        with pytest.raises(ValidationError):
            RawJobRecord.model_validate(data)

    def test_optional_fields_absent(self):
        """Missing optional fields must be filled with standard defaults (None or [])."""
        data = {
            "source": "remotive",
            "title": "DevOps Specialist",
        }
        record = RawJobRecord.model_validate(data)
        assert record.company is None
        assert record.url is None
        assert record.tags == []
        assert record.category is None

    def test_malformed_field_types(self):
        """Invalid types (e.g. integer for source) must raise validation error."""
        data = {
            "source": 12345,  # Should be string
            "title": "Developer",
        }
        # Pydantic may coerce 12345 to "12345". Let's test with a structure like a list.
        data_bad = {
            "source": ["not", "a", "string"],
            "title": "Developer",
        }
        with pytest.raises(ValidationError):
            RawJobRecord.model_validate(data_bad)

    def test_validate_records_batch(self):
        """validate_records must split a batch into valid objects and error messages."""
        batch = [
            {"source": "remotive", "title": "Valid Job A", "url": "https://a.com"},
            {"source": "remotive", "title": "   ", "url": None},  # Invalid (both empty)
            {"source": "remotive", "title": "Valid Job B", "company": "Co"},
        ]
        valid, errors = validate_records(batch)
        assert len(valid) == 2
        assert len(errors) == 1
        assert "Valid Job A" in valid[0].title
        assert "Valid Job B" in valid[1].title
        assert "Record 1" in errors[0]
