"""Tests for scheduler/runner.py — pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from infodigest.config import Config
from infodigest.scheduler.runner import RunReport, run, _load_sources, _load_rater_config


class TestRunReport:
    def test_default_state(self) -> None:
        report = RunReport()
        assert report.status == "running"
        assert report.collected == 0
        assert report.duration_seconds is None

    def test_duration_after_end(self) -> None:
        from datetime import timedelta
        report = RunReport()
        report.ended_at = report.started_at + timedelta(seconds=10)
        assert report.duration_seconds == pytest.approx(10.0, abs=1.0)


class TestLoadSources:
    def test_load_sources(self, full_config: Config) -> None:
        sources = _load_sources(full_config.config_dir)
        assert len(sources) == 1
        assert sources[0].id == "test-feed"


class TestLoadRaterConfig:
    def test_load_rater_config(self, full_config: Config) -> None:
        cfg = _load_rater_config(full_config.config_dir)
        assert cfg.weights["authority"] == 30
        assert cfg.push_grade_min == "B"


class TestRun:
    def test_run_with_fetch_failure(self, full_config: Config) -> None:
        """Run should complete even if fetching fails."""
        with patch("infodigest.scheduler.runner.Fetcher") as MockFetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch.side_effect = Exception("Network error")
            mock_fetcher.close = MagicMock()
            MockFetcher.return_value = mock_fetcher

            report = run(full_config)

        assert report.status == "success"  # No entries is still success
        assert report.collected == 0
        assert report.sources_failed == 1

    def test_run_with_no_sources(self, full_config: Config) -> None:
        """Run with empty feeds.yaml should succeed."""
        (full_config.config_dir / "feeds.yaml").write_text("sources: []\n")
        report = run(full_config)
        assert report.status == "success"
        assert report.collected == 0

    def test_run_with_sample_feed(self, full_config: Config, fixtures_dir: Path) -> None:
        """Run with a real sample feed should collect and rate entries."""
        sample_feed = (fixtures_dir / "rss2_sample.xml").read_bytes()

        with patch("infodigest.scheduler.runner.Fetcher") as MockFetcher:
            from infodigest.collector.fetcher import FetchResult
            mock_fetcher = MagicMock()
            mock_fetcher.fetch.return_value = FetchResult(
                content=sample_feed,
                status_code=200,
                etag='"v1"',
                last_modified="Mon, 30 Jun 2026 10:00:00 GMT",
            )
            mock_fetcher.close = MagicMock()
            MockFetcher.return_value = mock_fetcher

            report = run(full_config)

        assert report.collected == 3
        assert report.deduped == 3
        assert report.rated == 3
        assert report.status == "success"
