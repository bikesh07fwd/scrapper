"""
tests/test_base_adapter.py — Tests for the BaseAdapter abstract interface.

Verifies that:
  - BaseAdapter cannot be instantiated directly (it is abstract)
  - Concrete subclasses must implement both fetch() and parse()
  - source_label() defaults to name and can be overridden
  - The parse() contract (returns a list) is enforceable
"""

import pytest
from adapters.base import BaseAdapter


# ─── Helpers: concrete subclasses used in tests ───────────────────────────────

class FullAdapter(BaseAdapter):
    """Minimal valid implementation — used to verify happy-path behaviour."""
    name = "full"

    async def fetch(self) -> bytes:
        return b""

    def parse(self, raw) -> list[dict]:
        return [{"title": "Job A"}]


class CustomLabelAdapter(BaseAdapter):
    """Overrides source_label() to verify the override mechanism."""
    name = "custom"

    async def fetch(self) -> bytes:
        return b""

    def parse(self, raw) -> list[dict]:
        return []

    def source_label(self) -> str:
        return "Custom Source Label"


# ─── Instantiation: abstract class must not be usable directly ────────────────

class TestAbstractEnforcement:

    def test_cannot_instantiate_base_adapter_directly(self):
        """BaseAdapter is abstract — instantiation must raise TypeError."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseAdapter()

    def test_subclass_missing_both_methods_cannot_be_instantiated(self):
        """A subclass that implements neither fetch nor parse is still abstract."""
        class BothMissing(BaseAdapter):
            name = "missing_both"

        with pytest.raises(TypeError):
            BothMissing()

    def test_subclass_missing_fetch_cannot_be_instantiated(self):
        """Implementing only parse() is not sufficient."""
        class MissingFetch(BaseAdapter):
            name = "no_fetch"
            def parse(self, raw) -> list[dict]:
                return []

        with pytest.raises(TypeError):
            MissingFetch()

    def test_subclass_missing_parse_cannot_be_instantiated(self):
        """Implementing only fetch() is not sufficient."""
        class MissingParse(BaseAdapter):
            name = "no_parse"
            async def fetch(self) -> bytes:
                return b""

        with pytest.raises(TypeError):
            MissingParse()

    def test_complete_subclass_can_be_instantiated(self):
        """A subclass with both methods can be instantiated without error."""
        adapter = FullAdapter()
        assert adapter is not None


# ─── source_label() ───────────────────────────────────────────────────────────

class TestSourceLabel:

    def test_default_source_label_returns_name(self):
        """If source_label() is not overridden, it returns self.name."""
        adapter = FullAdapter()
        assert adapter.source_label() == "full"

    def test_overridden_source_label_is_used(self):
        """A subclass can override source_label() with a custom string."""
        adapter = CustomLabelAdapter()
        assert adapter.source_label() == "Custom Source Label"

    def test_source_label_is_not_empty(self):
        adapter = FullAdapter()
        assert len(adapter.source_label()) > 0


# ─── parse() contract ─────────────────────────────────────────────────────────

class TestParseContract:

    def test_parse_returns_a_list(self):
        """parse() must always return a list."""
        adapter = FullAdapter()
        result = adapter.parse(b"anything")
        assert isinstance(result, list)

    def test_parse_returns_dicts(self):
        """Each item in the result must be a dict."""
        adapter = FullAdapter()
        result = adapter.parse(b"anything")
        for item in result:
            assert isinstance(item, dict)

    def test_parse_accepts_bytes(self):
        """parse() must accept bytes input without raising."""
        adapter = FullAdapter()
        result = adapter.parse(b"raw bytes")
        assert isinstance(result, list)

    def test_parse_accepts_string(self):
        """parse() must accept str input without raising."""
        adapter = FullAdapter()
        result = adapter.parse("raw string")
        assert isinstance(result, list)


# ─── name attribute ───────────────────────────────────────────────────────────

class TestNameAttribute:

    def test_name_is_accessible(self):
        adapter = FullAdapter()
        assert adapter.name == "full"

    def test_name_matches_source_label_by_default(self):
        adapter = FullAdapter()
        assert adapter.name == adapter.source_label()
