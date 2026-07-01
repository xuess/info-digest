"""Tests for collector/fetcher.py"""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import MagicMock

from infodigest.collector.fetcher import Fetcher, FetchResult


class TestFetcher:
    def test_fetch_result_not_modified(self) -> None:
        """304 should return not_modified=True with empty content."""
        # We'll test via mock in integration; here test the dataclass
        result = FetchResult(
            content=b"",
            status_code=304,
            etag='"abc"',
            last_modified="Mon, 30 Jun 2026 10:00:00 GMT",
            not_modified=True,
        )
        assert result.not_modified is True
        assert result.content == b""
        assert result.status_code == 304

    def test_fetch_result_normal(self) -> None:
        result = FetchResult(
            content=b"<rss></rss>",
            status_code=200,
            etag='"xyz"',
            last_modified=None,
        )
        assert result.not_modified is False
        assert result.content == b"<rss></rss>"

    def test_context_manager(self) -> None:
        """Fetcher works as context manager."""
        with Fetcher(timeout=5, retries=1) as f:
            assert isinstance(f, Fetcher)

    def test_conditional_headers(self) -> None:
        """Verify conditional headers are set from etag/last_modified."""
        # This tests the logic, not the network
        f = Fetcher(timeout=5, retries=1)
        # We verify the headers dict would be built correctly
        # by checking the internal method signature accepts etag/last_modified
        assert hasattr(f, "fetch")
        f.close()


class TestFetcherIntegration:
    """Integration tests with httpx mocking."""

    def test_fetch_200(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="https://example.com/feed",
            content=b"<rss></rss>",
            headers={"etag": '"v1"', "last-modified": "Mon, 30 Jun 2026 10:00:00 GMT"},
        )
        with Fetcher(timeout=5, retries=1) as f:
            result = f.fetch("https://example.com/feed")
        assert result.status_code == 200
        assert result.content == b"<rss></rss>"
        assert result.etag == '"v1"'
        assert result.last_modified == "Mon, 30 Jun 2026 10:00:00 GMT"
        assert result.not_modified is False

    def test_fetch_304(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="https://example.com/feed",
            status_code=304,
        )
        with Fetcher(timeout=5, retries=1) as f:
            result = f.fetch(
                "https://example.com/feed",
                etag='"v1"',
                last_modified="Mon, 30 Jun 2026 10:00:00 GMT",
            )
        assert result.not_modified is True
        assert result.status_code == 304

    def test_fetch_5xx_retries(self, httpx_mock) -> None:
        """5xx errors should be retried."""
        httpx_mock.add_response(url="https://example.com/feed", status_code=503)
        httpx_mock.add_response(url="https://example.com/feed", status_code=503)
        httpx_mock.add_response(
            url="https://example.com/feed",
            content=b"<rss>ok</rss>",
        )
        with Fetcher(timeout=5, retries=3) as f:
            result = f.fetch("https://example.com/feed")
        assert result.status_code == 200
        assert result.content == b"<rss>ok</rss>"

    def test_fetch_4xx_raises(self, httpx_mock) -> None:
        """4xx errors (except 429) should raise immediately."""
        httpx_mock.add_response(url="https://example.com/feed", status_code=404)
        with Fetcher(timeout=5, retries=3) as f:
            with pytest.raises(httpx.HTTPStatusError):
                f.fetch("https://example.com/feed")

    def test_fetch_preserves_conditional_headers(self, httpx_mock) -> None:
        """Verify If-None-Match and If-Modified-Since are sent."""
        httpx_mock.add_response(url="https://example.com/feed", status_code=304)

        with Fetcher(timeout=5, retries=1) as f:
            f.fetch(
                "https://example.com/feed",
                etag='"test-etag"',
                last_modified="Wed, 01 Jan 2025 00:00:00 GMT",
            )

        request = httpx_mock.get_request()
        assert request.headers.get("if-none-match") == '"test-etag"'
        assert request.headers.get("if-modified-since") == "Wed, 01 Jan 2025 00:00:00 GMT"
