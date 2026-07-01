"""Tests for cli.py — command-line interface."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from infodigest.config import Config
from infodigest.cli import main


class TestCLI:
    def test_no_command(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 1

    def test_help(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0

    def test_run_subcommand(self, full_config: Config, fixtures_dir: Path) -> None:
        """Run subcommand should execute pipeline."""
        from infodigest.collector.fetcher import FetchResult

        sample_feed = (fixtures_dir / "rss2_sample.xml").read_bytes()

        with patch("infodigest.scheduler.runner.Fetcher") as MockFetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch.return_value = FetchResult(
                content=sample_feed,
                status_code=200,
                etag='"v1"',
                last_modified=None,
            )
            mock_fetcher.close = MagicMock()
            MockFetcher.return_value = mock_fetcher

            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                main(["-c", str(full_config.config_dir), "run"])

            output = f.getvalue()
            assert "Run Report" in output
            assert "Collected" in output
