"""
pipeline/normalizer.py — Converts RawJobRecord objects to canonical format.

Responsibilities:
- Cleanup title: strip, unescape HTML entities.
- Cleanup company: strip, fallback to "Unknown" if missing.
- Normalize location: case-insensitive Remote checks.
- Deduplicate and clean tags.
- Parse published_at timestamp to timezone-aware UTC datetime.
- Clean description: strip HTML, normalize whitespace, truncate to 500 chars.
- Generate a stable external_id: sha256(source + "|" + canonical_url).
"""

import hashlib
import re
import html
import json
from datetime import datetime, timezone
from typing import Optional

from pipeline.validator import RawJobRecord


def strip_html_tags(text: Optional[str]) -> str:
    """
    Remove all HTML tags and unescape common HTML entities.
    """
    if not text:
        return ""
    # Unescape HTML entities like &amp; -> &
    text = html.unescape(text)
    # Simple regex to strip HTML tags
    cleaned = re.sub(r"<[^>]*>", "", text)
    # Normalize all whitespaces (spaces, tabs, newlines) to a single space
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def normalize_location(loc: Optional[str]) -> Optional[str]:
    """
    Normalizes location values. Case-insensitively maps explicit remote/anywhere
    values to "Remote", while preserving other specific regions or countries.
    """
    if not loc:
        return "Remote"  # Default remote for remote-only feeds like Remotive

    cleaned = loc.strip()
    lower_val = cleaned.lower()

    # If it represents any common remote keywords
    remote_keywords = {
        "remote",
        "anywhere",
        "worldwide",
        "everywhere",
        "work from home",
        "wfh",
        "anywhere in the world",
    }
    if lower_val in remote_keywords or any(kw in lower_val for kw in ["anywhere", "worldwide"]):
        return "Remote"

    return cleaned


def normalize_published_at(parsed_str: Optional[str]) -> datetime:
    """
    Parses ISO8601 published timestamp to a timezone-aware UTC datetime.
    Falls back to current time in UTC if parsing fails or input is missing.
    """
    fallback_dt = datetime.now(timezone.utc)
    if not parsed_str:
        return fallback_dt

    try:
        # Standard ISO format: "YYYY-MM-DDTHH:MM:SSZ" or similar
        # Replace Z with +00:00 for datetime.fromisoformat compatibility
        cleaned_str = parsed_str.strip()
        if cleaned_str.endswith("Z"):
            cleaned_str = cleaned_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned_str)
        # Ensure it is timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return fallback_dt


def compute_external_id(source: str, url: Optional[str]) -> str:
    """
    Generates a deterministic hash identifier for a job:
    sha256(source + "|" + canonical_url)
    """
    url_canonical = (url or "").strip()
    hash_input = f"{source.strip()}|{url_canonical}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


def normalize_record(raw: RawJobRecord) -> dict:
    """
    Normalizes a single validated RawJobRecord into canonical database-ready format.
    """
    source = raw.source.strip()
    url = raw.url.strip() if raw.url else None

    # Canonical Title
    title = strip_html_tags(raw.title)
    if not title and url:
        # Fallback to a placeholder if title was somehow stripped completely but URL exists
        title = "Job Listing"

    # Canonical Company
    company = strip_html_tags(raw.company)
    if not company:
        company = "Unknown"

    # Canonical Location
    location = normalize_location(raw.location)

    # Tags deduplication and formatting
    cleaned_tags = []
    seen_tags = set()
    for tag in raw.tags:
        t_clean = tag.strip()
        if t_clean and t_clean.lower() not in seen_tags:
            cleaned_tags.append(t_clean)
            seen_tags.add(t_clean.lower())

    # Remotive uses category as tags occasionally; ensure category is clean
    category = strip_html_tags(raw.category) or None

    # Description snippet (HTML stripped, truncated to 500 chars)
    desc_clean = strip_html_tags(raw.description_html)
    description_snippet = desc_clean[:500] if desc_clean else None

    # Timestamp conversion
    published_at = normalize_published_at(raw.published_parsed)

    # Deterministic external_id
    external_id = compute_external_id(source, url)

    # Store raw source record serialized for post-mortem debugging
    raw_json_str = raw.model_dump_json()

    return {
        "external_id": external_id,
        "source": source,
        "title": title,
        "company": company,
        "location": location,
        "category": category,
        "tags": json.dumps(cleaned_tags) if cleaned_tags else None,
        "url": url,
        "description_snippet": description_snippet,
        "published_at": published_at,
        "raw_json": raw_json_str,
    }
