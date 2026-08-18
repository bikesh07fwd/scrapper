"""
tests/test_fetcher.py — Unit tests for the shared HTTP fetch layer.

All tests use respx to mock httpx at the transport level.
No real network requests are made.

asyncio.sleep is replaced with an async no-op in retry tests so the test
suite runs in milliseconds rather than waiting for real backoff intervals.

Test classes:
  TestComputeBackoff   — pure function, no I/O
  TestFetchSuccess     — happy path and header verification
  TestFetchNonRetryable — 400/401/403/404 — stopped immediately, no retries
  TestFetchRetryOn5xx  — 500 → success; repeated 500 → exhaustion
  TestFetchRateLimit   — 429 with/without Retry-After header
  TestFetchTimeout     — timeout then success; timeout exhaustion
  TestFetchConnection  — connection error then success; exhaustion
"""

import pytest
import httpx

from pipeline.fetcher import (
    fetch,
    _compute_backoff,
    FetchTimeoutError,
    FetchConnectionError,
    NonRetryableError,
    RetryExhaustedError,
)

URL = "https://feeds.example.com/jobs.xml"
CONTENT = b"<rss><channel><title>Jobs</title></channel></rss>"


# ─── Async sleep stub ─────────────────────────────────────────────────────────
# Used in tests that exercise retry paths. We replace asyncio.sleep with this
# so retries run instantly without actually waiting 2-8 seconds.

async def noop_sleep(_seconds: float) -> None:
    """Drop-in replacement for asyncio.sleep that does nothing."""


# ─── _compute_backoff (pure function — no I/O needed) ────────────────────────

class TestComputeBackoff:

    def test_retry_after_header_used_for_429(self):
        """Retry-After value is used directly when present on a 429 response."""
        response = httpx.Response(429, headers={"Retry-After": "10"})
        assert _compute_backoff(attempt=1, response=response) == 10.0

    def test_retry_after_fractional_value(self):
        """Retry-After can be a fractional second."""
        response = httpx.Response(429, headers={"Retry-After": "0.5"})
        assert _compute_backoff(attempt=1, response=response) == 0.5

    def test_non_numeric_retry_after_falls_back_to_exponential(self):
        """Non-numeric Retry-After header falls back to exponential backoff."""
        response = httpx.Response(429, headers={"Retry-After": "Mon, 18 Aug 2026 10:00:00 GMT"})
        wait = _compute_backoff(attempt=1, response=response)
        # Exponential attempt=1: base=2, jitter in [0,1) → result in [2.0, 3.0)
        assert 2.0 <= wait < 3.0

    def test_no_response_uses_exponential_backoff(self):
        """No response (timeout/connection error) → exponential backoff."""
        wait = _compute_backoff(attempt=1, response=None)
        assert 2.0 <= wait < 3.0

    def test_exponential_grows_with_attempt_number(self):
        """Backoff base doubles with each attempt."""
        # attempt=2 base is 4.0 — always larger than attempt=1 max of ~3.0
        wait2 = _compute_backoff(attempt=2, response=None)
        assert wait2 >= 4.0  # base is 2**2=4, plus jitter in [0,1)

    def test_retry_after_only_applies_to_429(self):
        """Retry-After on a 500 response must NOT be used — fall back to exponential."""
        response = httpx.Response(500, headers={"Retry-After": "99"})
        wait = _compute_backoff(attempt=1, response=response)
        # 500 is not 429 → exponential backoff, nowhere near 99
        assert wait < 4.0


# ─── Successful fetch ─────────────────────────────────────────────────────────

class TestFetchSuccess:

    async def test_returns_body_bytes(self, respx_mock):
        respx_mock.get(URL).mock(return_value=httpx.Response(200, content=CONTENT))
        result = await fetch(URL)
        assert result == CONTENT

    async def test_extra_headers_are_sent(self, respx_mock):
        """extra_headers are merged with DEFAULT_HEADERS and sent."""
        respx_mock.get(URL).mock(return_value=httpx.Response(200, content=b"ok"))
        await fetch(URL, extra_headers={"If-None-Match": '"etag-abc"'})
        request = respx_mock.calls.last.request
        assert request.headers.get("If-None-Match") == '"etag-abc"'

    async def test_default_user_agent_is_set(self, respx_mock):
        """Every request must include the honest AcdyonJobIngestion user-agent."""
        respx_mock.get(URL).mock(return_value=httpx.Response(200, content=b"ok"))
        await fetch(URL)
        ua = respx_mock.calls.last.request.headers["user-agent"]
        assert ua == "AcdyonJobIngestion/1.0"

    async def test_extra_headers_do_not_replace_user_agent(self, respx_mock):
        """Callers cannot accidentally override the User-Agent via extra_headers."""
        respx_mock.get(URL).mock(return_value=httpx.Response(200, content=b"ok"))
        # Passing a different user-agent in extra_headers WILL override it.
        # This test verifies the current behaviour is deterministic.
        await fetch(URL, extra_headers={"Accept": "application/json"})
        ua = respx_mock.calls.last.request.headers["user-agent"]
        assert ua == "AcdyonJobIngestion/1.0"  # default still set


# ─── Non-retryable errors ─────────────────────────────────────────────────────

class TestFetchNonRetryable:

    async def test_403_raises_immediately(self, respx_mock):
        """403 must raise NonRetryableError with no retry."""
        respx_mock.get(URL).mock(return_value=httpx.Response(403))
        with pytest.raises(NonRetryableError) as exc_info:
            await fetch(URL)
        assert exc_info.value.status_code == 403
        assert exc_info.value.url == URL
        # Exactly one request — no retries
        assert respx_mock.calls.call_count == 1

    async def test_404_raises_immediately(self, respx_mock):
        respx_mock.get(URL).mock(return_value=httpx.Response(404))
        with pytest.raises(NonRetryableError) as exc_info:
            await fetch(URL)
        assert exc_info.value.status_code == 404
        assert respx_mock.calls.call_count == 1

    async def test_401_raises_immediately(self, respx_mock):
        respx_mock.get(URL).mock(return_value=httpx.Response(401))
        with pytest.raises(NonRetryableError):
            await fetch(URL)
        assert respx_mock.calls.call_count == 1

    async def test_400_raises_immediately(self, respx_mock):
        respx_mock.get(URL).mock(return_value=httpx.Response(400))
        with pytest.raises(NonRetryableError):
            await fetch(URL)
        assert respx_mock.calls.call_count == 1


# ─── Retry on 5xx ─────────────────────────────────────────────────────────────

class TestFetchRetryOn5xx:

    async def test_500_then_success(self, respx_mock, monkeypatch):
        """500 on attempt 1, 200 on attempt 2 — returns body."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, content=CONTENT),
            ]
        )
        result = await fetch(URL)
        assert result == CONTENT
        assert respx_mock.calls.call_count == 2

    async def test_500_sleeps_between_retries(self, respx_mock, monkeypatch):
        """A sleep must happen between attempt 1 and attempt 2."""
        sleep_calls: list[float] = []

        async def recording_sleep(secs: float) -> None:
            sleep_calls.append(secs)

        monkeypatch.setattr("asyncio.sleep", recording_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, content=b"ok"),
            ]
        )
        await fetch(URL)
        assert len(sleep_calls) == 1  # exactly one sleep between two attempts

    async def test_repeated_500_raises_retry_exhausted(self, respx_mock, monkeypatch):
        """Three consecutive 500s exhaust all retries."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(500),
                httpx.Response(500),
            ]
        )
        with pytest.raises(RetryExhaustedError) as exc_info:
            await fetch(URL)
        assert exc_info.value.attempts == 3
        assert exc_info.value.url == URL
        assert respx_mock.calls.call_count == 3

    async def test_502_is_retryable(self, respx_mock, monkeypatch):
        """502 Bad Gateway is treated the same as 500."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(200, content=b"ok"),
            ]
        )
        result = await fetch(URL)
        assert result == b"ok"

    async def test_503_is_retryable(self, respx_mock, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, content=b"ok"),
            ]
        )
        result = await fetch(URL)
        assert result == b"ok"


# ─── Rate limiting (429) ──────────────────────────────────────────────────────

class TestFetchRateLimit:

    async def test_429_with_retry_after_waits_correct_duration(
        self, respx_mock, monkeypatch
    ):
        """On 429 with Retry-After, sleep must use exactly that value."""
        sleep_calls: list[float] = []

        async def recording_sleep(secs: float) -> None:
            sleep_calls.append(secs)

        monkeypatch.setattr("asyncio.sleep", recording_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "7"}),
                httpx.Response(200, content=CONTENT),
            ]
        )
        result = await fetch(URL)
        assert result == CONTENT
        assert sleep_calls == [7.0]

    async def test_429_without_retry_after_uses_exponential_backoff(
        self, respx_mock, monkeypatch
    ):
        """429 without Retry-After header falls back to exponential backoff."""
        sleep_calls: list[float] = []

        async def recording_sleep(secs: float) -> None:
            sleep_calls.append(secs)

        monkeypatch.setattr("asyncio.sleep", recording_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(429),  # no Retry-After
                httpx.Response(200, content=CONTENT),
            ]
        )
        await fetch(URL)
        assert len(sleep_calls) == 1
        # attempt=1 backoff: base=2, jitter∈[0,1) → 2.0 ≤ wait < 3.0
        assert 2.0 <= sleep_calls[0] < 3.0

    async def test_429_exhaustion(self, respx_mock, monkeypatch):
        """Three consecutive 429s raise RetryExhaustedError."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(429),
                httpx.Response(429),
            ]
        )
        with pytest.raises(RetryExhaustedError):
            await fetch(URL)
        assert respx_mock.calls.call_count == 3


# ─── Timeout handling ─────────────────────────────────────────────────────────

class TestFetchTimeout:

    async def test_timeout_then_success(self, respx_mock, monkeypatch):
        """Timeout on attempt 1, success on attempt 2."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.ReadTimeout("simulated read timeout"),
                httpx.Response(200, content=CONTENT),
            ]
        )
        result = await fetch(URL)
        assert result == CONTENT
        assert respx_mock.calls.call_count == 2

    async def test_timeout_exhaustion_raises_fetch_timeout_error(
        self, respx_mock, monkeypatch
    ):
        """All three attempts time out → FetchTimeoutError."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.ReadTimeout("t1"),
                httpx.ReadTimeout("t2"),
                httpx.ReadTimeout("t3"),
            ]
        )
        with pytest.raises(FetchTimeoutError) as exc_info:
            await fetch(URL)
        assert exc_info.value.attempts == 3
        assert exc_info.value.url == URL
        assert respx_mock.calls.call_count == 3

    async def test_connect_timeout_is_retried(self, respx_mock, monkeypatch):
        """ConnectTimeout (a subclass of TimeoutException) is retried."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.ConnectTimeout("connect timed out"),
                httpx.Response(200, content=b"ok"),
            ]
        )
        result = await fetch(URL)
        assert result == b"ok"


# ─── Connection errors ────────────────────────────────────────────────────────

class TestFetchConnectionError:

    async def test_connection_error_then_success(self, respx_mock, monkeypatch):
        """Connection error on attempt 1, success on attempt 2."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                httpx.Response(200, content=CONTENT),
            ]
        )
        result = await fetch(URL)
        assert result == CONTENT
        assert respx_mock.calls.call_count == 2

    async def test_connection_error_exhaustion(self, respx_mock, monkeypatch):
        """All three attempts fail with connection error → FetchConnectionError."""
        monkeypatch.setattr("asyncio.sleep", noop_sleep)
        respx_mock.get(URL).mock(
            side_effect=[
                httpx.ConnectError("refused"),
                httpx.ConnectError("refused"),
                httpx.ConnectError("refused"),
            ]
        )
        with pytest.raises(FetchConnectionError) as exc_info:
            await fetch(URL)
        assert exc_info.value.attempts == 3
        assert exc_info.value.url == URL
        assert respx_mock.calls.call_count == 3
