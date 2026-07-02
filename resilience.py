"""Shared retry/backoff helper for transient external-I/O failures.

One rule set, used at every boundary that talks to the network:

- retry with exponential backoff only on *transient* failures (rate limits,
  timeouts, connection drops, 5xx) — permanent failures (4xx other than 429,
  parse errors, auth) re-raise immediately
- every retry is logged with context; the last attempt's exception propagates
  to the caller, whose existing failure semantics are unchanged (sources still
  log-and-return-[], the summarizer still raises, etc.)

Boundaries that deliberately do NOT retry:
- RSS: feedparser captures network errors in `bozo` rather than raising, and a
  bad feed is usually malformed rather than transient.
- Scraper enrichment: best-effort per item; failures are dominated by paywalls
  and blocks (permanent), and retrying would multiply run time per item.
- SQLite: `PRAGMA busy_timeout` in store.py handles transient lock contention
  at the driver level; a write that still fails raises to the caller.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SECONDS = 1.0

_TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504, 529}


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    label: str,
    is_transient: Callable[[Exception], bool],
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
) -> T:
    """Call `fn`, retrying transient failures with exponential backoff.

    Retries up to `attempts` total tries, sleeping base_delay * 2**n between
    them. Non-transient exceptions, and the final failed attempt, re-raise —
    the caller keeps its own failure semantics.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts or not is_transient(exc):
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "%s: transient failure (%s: %s) — retrying in %.1fs (attempt %d/%d)",
                label, type(exc).__name__, exc, delay, attempt, attempts,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def is_transient_http(exc: Exception) -> bool:
    """Transient for requests-based fetchers: timeouts, connection drops,
    and 429/5xx responses."""
    import requests

    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in _TRANSIENT_HTTP_STATUSES
    return False


def is_transient_arxiv(exc: Exception) -> bool:
    """Transient for the arxiv package: rate-limit/5xx HTTP errors and empty
    pages the API intermittently returns under load."""
    import arxiv

    if isinstance(exc, arxiv.UnexpectedEmptyPageError):
        return True
    if isinstance(exc, arxiv.HTTPError):
        return getattr(exc, "status", None) in _TRANSIENT_HTTP_STATUSES
    return False


def is_transient_anthropic(exc: Exception) -> bool:
    """Transient for the Anthropic API: rate limits, overload, connection
    failures, and 5xx. Auth/bad-request errors are permanent."""
    import anthropic

    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in _TRANSIENT_HTTP_STATUSES
    return False
