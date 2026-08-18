"""
adapters/base.py — Abstract base class for all job source adapters.

Design contract:
    Every adapter does exactly two things:
      1. fetch()  — retrieve raw content from the source
      2. parse()  — convert that raw content into a list of raw record dicts

    Everything else (validation, normalization, deduplication, persistence)
    belongs to the shared ingestion pipeline — not the adapter.

Why this separation matters:
    - parse() can be tested with a local fixture file, no network needed
    - Each adapter is independently swappable without touching the pipeline
    - Adding a new source means adding a new file that inherits this class

Current adapter tree:
    BaseAdapter
    ├── RemotiveRSSAdapter   (adapters/remotive_rss.py)
    └── SandboxAdapter       (adapters/sandbox.py — Phase 4)
"""

from abc import ABC, abstractmethod
from typing import Union


class BaseAdapter(ABC):
    """
    Abstract base class that defines the adapter interface.

    Subclasses must:
      - Set `name` as a class-level string (e.g., name = "remotive")
      - Implement `fetch()` as an async method
      - Implement `parse()` as a sync method

    Subclasses should NOT:
      - Write to the database
      - Validate or normalize field values
      - Deduplicate records
    """

    # Each subclass declares its own name at the class level.
    # Example:  name = "remotive"
    name: str

    @abstractmethod
    async def fetch(self) -> Union[str, bytes]:
        """
        Retrieve raw content from the source.

        Returns bytes or str depending on the source format.
        The caller (the pipeline runner) passes this directly to parse().

        Raises:
            FetchError (or a subclass) if the request fails permanently.
        """
        ...

    @abstractmethod
    def parse(self, raw: Union[str, bytes]) -> list[dict]:
        """
        Convert raw source content into a list of raw record dicts.

        Each dict contains source-specific field names — not yet
        normalized to the canonical JobRecord schema.

        Contract:
          - Always returns a list (may be empty).
          - Never raises on a malformed individual record; log and skip instead.
          - Never calls the database.
          - Accepts bytes or str from a fixture file for offline testing.

        Args:
            raw: The exact bytes/str returned by fetch().

        Returns:
            List of raw dicts, one per job entry found in the source.
        """
        ...

    def source_label(self) -> str:
        """
        Human-readable name for this source.

        Used in structured log records, ingestion_runs rows, and the
        dashboard adapter health panel.

        Defaults to `self.name`. Override in a subclass only if the
        display name should differ from the adapter identifier.
        """
        return self.name
