"""Small stdlib HTTP client with timeouts, retries and exponential backoff.

Sources are public endpoints with no SLA. Every response is validated by the caller; this layer only
retries transport errors, 429 and 5xx.
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable

log = logging.getLogger(__name__)
USER_AGENT = "QuantSynthica-research/0.1 (non-commercial research; polite rate limits)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


def fetch(
    url: str, *, timeout: float = 60, retries: int = 4, backoff: float = 1.5,
    validate: Callable[[bytes], None] | None = None, sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """GET `url`. `validate` may raise ValueError for an incomplete/invalid body, which triggers a retry."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            if validate is not None:
                validate(body)
            return body
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in RETRY_STATUS:
                raise FetchError(f"HTTP {exc.code} for {url}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
            last = exc
        if attempt < retries:
            delay = backoff * (2**attempt)
            log.warning("fetch retry", extra={"url": url, "attempt": attempt + 1, "error": repr(last), "sleep": delay})
            sleep(delay)
    raise FetchError(f"giving up on {url}: {last!r}") from last
