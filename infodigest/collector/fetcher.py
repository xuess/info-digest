"""HTTP fetcher with ETag/Last-Modified incremental support."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 3
DEFAULT_USER_AGENT = "InfoDigest/1.0"


@dataclass(frozen=True)
class FetchResult:
    """Result of fetching a feed URL."""
    content: bytes
    status_code: int
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


class Fetcher:
    """HTTP fetcher with incremental support (ETag/Last-Modified)."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._timeout = timeout
        self._retries = retries
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def fetch(
        self,
        url: str,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult:
        """Fetch a URL with optional conditional headers.

        Returns FetchResult with content, or not_modified=True on 304.
        Raises on persistent failure after retries.
        """
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        last_exc: Exception | None = None
        for attempt in range(self._retries):
            try:
                resp = self._client.get(url, headers=headers)

                if resp.status_code == 304:
                    return FetchResult(
                        content=b"",
                        status_code=304,
                        etag=etag,
                        last_modified=last_modified,
                        not_modified=True,
                    )

                resp.raise_for_status()
                return FetchResult(
                    content=resp.content,
                    status_code=resp.status_code,
                    etag=resp.headers.get("etag"),
                    last_modified=resp.headers.get("last-modified"),
                )

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if 400 <= status < 500 and status != 429:
                    logger.warning("Client error %d for %s, not retrying", status, url)
                    raise
                if status == 429:
                    logger.warning("Rate limited (429) for %s, waiting 60s", url)
                    time.sleep(60)
                    continue
                last_exc = exc
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc

            wait = 2 ** attempt
            logger.info("Retry %d/%d for %s in %ds", attempt + 1, self._retries, url, wait)
            time.sleep(wait)

        raise last_exc  # type: ignore[misc]
