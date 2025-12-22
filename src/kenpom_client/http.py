from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx

from .exceptions import (
    KenPomAuthError,
    KenPomClientError,
    KenPomRateLimitError,
    KenPomServerError,
)

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, rps: float) -> None:
        self.min_interval = 0.0 if rps <= 0 else (1.0 / rps)
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.time()
        elapsed = now - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.time()


def request_json(
    *,
    client: httpx.Client,
    method: str,
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]],
    timeout: float,
    max_retries: int,
    backoff_base: float,
    rate_limiter: RateLimiter,
) -> Any:
    """
    Robust request with:
      - basic rate limiting
      - exponential backoff
      - friendly error classification
    """
    attempt = 0
    last_exc: Exception | None = None

    while attempt <= max_retries:
        attempt += 1
        rate_limiter.wait()
        try:
            resp = client.request(method, url, headers=headers, params=params, timeout=timeout)
            status = resp.status_code

            if status in (401, 403):
                raise KenPomAuthError(f"Auth failed (HTTP {status}). Check Bearer token.")

            if status == 429:
                raise KenPomRateLimitError("Rate limited (HTTP 429). Reduce RPS or back off.")

            if 500 <= status <= 599:
                raise KenPomServerError(f"Server error (HTTP {status}).")

            if 400 <= status <= 499:
                raise KenPomClientError(f"Client error (HTTP {status}): {resp.text[:200]}")

            return resp.json()

        except (
            KenPomRateLimitError,
            KenPomServerError,
            httpx.TimeoutException,
            httpx.TransportError,
        ) as e:
            last_exc = e
            if attempt > max_retries:
                break
            sleep_s = backoff_base * (2 ** (attempt - 1))
            # small cap to avoid runaway
            sleep_s = min(sleep_s, 15.0)
            log.warning(
                "Request failed (%s). Retry %s/%s in %.2fs",
                type(e).__name__,
                attempt,
                max_retries,
                sleep_s,
            )
            time.sleep(sleep_s)

    raise KenPomClientError(f"Request ultimately failed after {max_retries} retries: {last_exc}")
