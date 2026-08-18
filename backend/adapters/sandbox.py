"""
adapters/sandbox.py — Sandbox adapter to simulate various failure/success scenarios.

This adapter fetches from our own local endpoint /sandbox/jobs?scenario=...
using the shared HTTP fetcher, then parses the returned RSS XML feed.
"""

from typing import Union, Optional
import feedparser

from adapters.base import BaseAdapter
from pipeline.fetcher import fetch as http_fetch


class SandboxAdapter(BaseAdapter):
    """
    Adapter used strictly for verifying pipeline resilience under controlled conditions.
    """

    name = "sandbox"

    def __init__(
        self,
        scenario: str = "happy_path",
        base_url: str = "http://127.0.0.1:8000/sandbox/jobs",
    ):
        self.scenario = scenario
        self.base_url = base_url

    async def fetch(self) -> bytes:
        """
        Fetch the simulated RSS feed from the local sandbox endpoint.
        """
        url = f"{self.base_url}?scenario={self.scenario}"
        return await http_fetch(url)

    def parse(self, raw: Union[str, bytes]) -> list[dict]:
        """
        Parses simulated RSS bytes using feedparser, mapping XML fields to raw records.
        If the scenario is 'schema_changed', feedparser will fail or return incompatible keys.
        """
        feed = feedparser.parse(raw)

        # Check for schema_changed trigger
        # We can force a parsing error or missing expected fields if the scenario is schema_changed
        if self.scenario == "schema_changed":
            raise ValueError("Parser Error: Simulated source schema change / incompatible markup.")

        if not feed.entries:
            return []

        records = []
        for entry in feed.entries:
            tags = [t.term for t in entry.get("tags", []) if hasattr(t, "term") and t.term]

            records.append({
                "source": self.name,
                "title": entry.get("title") or None,
                "company": entry.get("author") or None,
                "url": entry.get("link") or None,
                "location": entry.get("location") if "location" in entry else None,
                "tags": tags,
                "category": tags[0] if tags else None,
                "published_raw": entry.get("published") or None,
                "published_parsed": entry.get("published") or None,  # Will parse or fallback in normalizer
                "description_html": entry.get("summary") or None,
                "entry_id": entry.get("id") or entry.get("link") or None,
            })
        return records
