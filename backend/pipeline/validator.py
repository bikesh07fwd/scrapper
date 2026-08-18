"""
pipeline/validator.py — Validates raw job records before normalization.

Rules:
- A record must be structurally valid according to Pydantic.
- Missing both 'title' and 'url' is a fatal error; such records are rejected.
- Individual validation failures should be recorded and not crash the batch.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class RawJobRecord(BaseModel):
    """
    Pydantic schema representing a raw, un-normalized job record from an adapter.
    """
    source: str
    title: Optional[str] = None
    company: Optional[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    published_raw: Optional[str] = None
    published_parsed: Optional[str] = None
    description_html: Optional[str] = None
    entry_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def clean_empty_strings(cls, data: Any) -> Any:
        """
        Coerces empty strings or whitespace-only strings to None for title and url
        before validation, so that if they are whitespace-only, they are treated as missing.
        """
        if isinstance(data, dict):
            for field in ("title", "url", "company", "category", "published_raw", "published_parsed", "description_html"):
                val = data.get(field)
                if isinstance(val, str) and not val.strip():
                    data[field] = None
        return data

    @model_validator(mode="after")
    def validate_title_or_url_present(self) -> "RawJobRecord":
        title_val = self.title
        url_val = self.url

        if not title_val and not url_val:
            raise ValueError("Record must have at least a non-empty title or a non-empty url.")
        return self


def validate_records(raw_records: list[dict[str, Any]]) -> tuple[list[RawJobRecord], list[str]]:
    """
    Validates a list of raw record dictionaries.

    Args:
        raw_records: List of raw dicts from the adapter.

    Returns:
        A tuple of (list of validated RawJobRecord objects, list of error messages).
    """
    valid_records: list[RawJobRecord] = []
    errors: list[str] = []

    for index, record in enumerate(raw_records):
        try:
            validated = RawJobRecord.model_validate(record)
            valid_records.append(validated)
        except Exception as exc:
            title_snippet = record.get("title") or record.get("url") or "Unknown"
            error_msg = f"Record {index} ({title_snippet}): {exc}"
            errors.append(error_msg)

    return valid_records, errors
