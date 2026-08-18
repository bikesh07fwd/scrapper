"""
pipeline/fetcher.py — Shared HTTP fetch layer used by all source adapters.

Responsibilities:
  - Make GET requests with explicit connect + read timeouts
  - Retry on transient server errors (500, 502, 503, 504) and rate limiting (429)
  - Stop immediately on client errors (400, 401, 403, 404) — no retry
  - Apply exponential backoff with jitter between retries
  - Honor Retry-After headers on HTTP 429 responses
  - Follow redirects
  - Raise typed exceptions so the pipeline can distinguish failure modes

What this module deliberately does NOT do:
  - No browser fingerprint spoofing
  - No user-agent rotation to evade detection
  - No proxy support
  - No CAPTCHA handling
  - No circuit breaking (that is Phase 4)

The User-Agent is "AcdyonJobIngestion/1.0" — an honest identifier
appropriate for a client that fetches permitted public feeds.
"""

import asyncio
import random
from typing import Optional

import httpx
import structlog

from config import settings

logger = structlog.get_logger(__name__)

# ─── Status code sets ─────────────────────────────────────────────────────────

# These status codes indicate a transient server problem; worth retrying.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# These status codes indicate a permanent client-side problem.
# Retrying will produce the same result, so we stop immediately.
NON_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({400, 401, 403, 404})

# ─── Request headers ──────────────────────────────────────────────────────────

# Sent on every request.
# Note: this is NOT a browser user-agent. We identify ourselves honestly.
# The "extra_headers" parameter in fetch() allows callers to add
# ETag / If-Modified-Since for conditional requests when ready.
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "AcdyonJobIngestion/1.0",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── Exceptions ───────────────────────────────────────────────────────────────

class FetchError(Exception):
    """Base class for all fetch failures. Catch this to handle any fetch error."""


class NonRetryableError(FetchError):
    """
    The server returned 400, 401, 403, or 404.

    These indicate a permanent problem (bad URL, access denied, not found).
    The pipeline should log this and move on — do not retry.
    """

    def __init__(self, url: str, status_code: int) -> None:
        self.url = url
        self.status_code = status_code
        super().__init__(f"Non-retryable HTTP {status_code} for {url!r}")


class RetryExhaustedError(FetchError):
    """
    All retry attempts failed with a retryable HTTP error (5xx or 429).

    The pipeline should record this as a run failure and let the circuit
    breaker (Phase 4) decide whether to suspend the adapter.
    """

    def __init__(self, url: str, attempts: int, last_error: str) -> None:
        self.url = url
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"All {attempts} attempt(s) failed for {url!r}. Last: {last_error}"
        )


class FetchTimeoutError(FetchError):
    """
    The request timed out on every attempt.

    Raised when httpx.TimeoutException is raised on the last retry.
    """

    def __init__(self, url: str, attempts: int) -> None:
        self.url = url
        self.attempts = attempts
        super().__init__(f"Timed out after {attempts} attempt(s) for {url!r}")


class FetchConnectionError(FetchError):
    """
    A TCP connection could not be established on any attempt.

    Raised when httpx.ConnectError is raised on the last retry.
    """

    def __init__(self, url: str, attempts: int) -> None:
        self.url = url
        self.attempts = attempts
        super().__init__(
            f"Connection failed after {attempts} attempt(s) for {url!r}"
        )


# ─── Backoff helper ───────────────────────────────────────────────────────────

def _compute_backoff(attempt: int, response: Optional[httpx.Response]) -> float:
    """
    Return the number of seconds to wait before the next retry attempt.

    Priority order:
      1. If the response is HTTP 429 with a numeric Retry-After header,
         use that value exactly. This is the server telling us to back off.
      2. Otherwise, use exponential backoff with small random jitter:
           wait = (2 ** attempt) + uniform(0, 1)

    Why jitter? If multiple adapters fail simultaneously (e.g., Render restart),
    jitter prevents them from retrying in lockstep and hammering the source.

    Example values:
      attempt=1 → 2.0–3.0 s
      attempt=2 → 4.0–5.0 s
      attempt=3 → 8.0–9.0 s  (only reached if fetch_max_retries > 3)

    Args:
        attempt:  The current attempt number (1-indexed).
        response: The HTTP response, if one was received. None for connection/timeout errors.
    """
    if response is not None and response.status_code == 429:
        retry_after_header = response.headers.get("Retry-After")
        if retry_after_header is not None:
            try:
                return float(retry_after_header)
            except ValueError:
                pass  # Header present but not a plain number; fall through

    base = float(2 ** attempt)
    jitter = random.uniform(0.0, 1.0)
    return base + jitter


# ─── Main fetch function ──────────────────────────────────────────────────────

async def fetch(
    url: str,
    *,
    extra_headers: Optional[dict[str, str]] = None,
) -> bytes:
    """
    Fetch a URL and return the raw response body as bytes.

    Retries up to settings.fetch_max_retries times on transient errors,
    with exponential backoff between attempts.

    Args:
        url:           The URL to GET.
        extra_headers: Optional additional headers merged with DEFAULT_HEADERS.
                       Use this to pass ETag / If-Modified-Since for
                       conditional requests (future enhancement).

    Returns:
        Raw response body as bytes.

    Raises:
        NonRetryableError    — server returned 400/401/403/404
        FetchTimeoutError    — all attempts timed out
        FetchConnectionError — TCP connection failed on all attempts
        RetryExhaustedError  — retryable status (5xx/429) persisted through all attempts
    """
    # httpx.Timeout requires all four fields (connect, read, write, pool) if
    # using keyword arguments without a default. We set write/pool to None
    # (unlimited) since we only care about connect + read timeouts here.
    timeout = httpx.Timeout(
        connect=settings.fetch_timeout_connect,
        read=settings.fetch_timeout_read,
        write=None,
        pool=None,
    )

    headers = {**DEFAULT_HEADERS}
    if extra_headers:
        headers.update(extra_headers)

    log = logger.bind(url=url)
    last_error: str = "unknown"
    response: Optional[httpx.Response] = None

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
    ) as client:

        for attempt in range(1, settings.fetch_max_retries + 1):
            try:
                log.debug(
                    "fetch.attempt",
                    attempt=attempt,
                    max=settings.fetch_max_retries,
                )
                response = await client.get(url, headers=headers)

                # ── Non-retryable: client error or access denial ──────────
                if response.status_code in NON_RETRYABLE_STATUS_CODES:
                    log.warning(
                        "fetch.non_retryable",
                        status_code=response.status_code,
                        attempt=attempt,
                    )
                    raise NonRetryableError(url, response.status_code)

                # ── Retryable: server error or rate limit ─────────────────
                if response.status_code in RETRYABLE_STATUS_CODES:
                    last_error = f"HTTP {response.status_code}"

                    if attempt == settings.fetch_max_retries:
                        log.error(
                            "fetch.retry_exhausted",
                            status_code=response.status_code,
                            attempts=attempt,
                        )
                        raise RetryExhaustedError(url, attempt, last_error)

                    wait = _compute_backoff(attempt, response)
                    log.warning(
                        "fetch.retry",
                        attempt=attempt,
                        status_code=response.status_code,
                        wait_seconds=round(wait, 2),
                    )
                    await asyncio.sleep(wait)
                    continue

                # ── Success ───────────────────────────────────────────────
                log.debug(
                    "fetch.success",
                    status_code=response.status_code,
                    bytes=len(response.content),
                    attempt=attempt,
                )
                return response.content

            except NonRetryableError:
                raise  # already logged; do not retry

            except httpx.TimeoutException as exc:
                last_error = f"timeout ({type(exc).__name__})"
                if attempt == settings.fetch_max_retries:
                    log.error("fetch.timeout_exhausted", attempts=attempt)
                    raise FetchTimeoutError(url, attempt) from exc

                wait = _compute_backoff(attempt, None)
                log.warning(
                    "fetch.timeout_retry",
                    attempt=attempt,
                    wait_seconds=round(wait, 2),
                )
                await asyncio.sleep(wait)

            except httpx.ConnectError as exc:
                last_error = f"connect error: {exc}"
                if attempt == settings.fetch_max_retries:
                    log.error("fetch.connection_exhausted", attempts=attempt)
                    raise FetchConnectionError(url, attempt) from exc

                wait = _compute_backoff(attempt, None)
                log.warning(
                    "fetch.connect_retry",
                    attempt=attempt,
                    wait_seconds=round(wait, 2),
                )
                await asyncio.sleep(wait)

    # Unreachable in practice — the loop always returns or raises.
    # Kept to satisfy the type checker.
    raise RetryExhaustedError(url, settings.fetch_max_retries, last_error)
