"""Shared test fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Return a temporary config directory with minimal settings."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "settings.yaml").write_text(
        "storage:\n"
        "  db_path: data/test.db\n"
        "  failed_digests_dir: data/failed\n"
        "collector:\n"
        "  timeout: 10\n"
        "  retries: 1\n"
        "delivery:\n"
        "  feishu:\n"
        "    enabled: false\n"
        "  dingtalk:\n"
        "    enabled: false\n"
    )
    (cfg / "feeds.yaml").write_text("sources: []\n")
    (cfg / "rater.yaml").write_text(
        "weights:\n"
        "  authority: 30\n"
        "  freshness: 25\n"
        "  relevance: 25\n"
        "  uniqueness: 10\n"
        "  engagement: 10\n"
        "freshness_half_life_hours: 72\n"
        "max_age_hours: 168\n"
        "relevance_target: 3.0\n"
        "engagement_threshold: 200\n"
        "grade_thresholds:\n"
        "  A: 75\n"
        "  B: 50\n"
        "push_grade_min: B\n"
        "keywords: {}\n"
        "dedup_similarity: 0.8\n"
        "dedup_window_days: 7\n"
    )
    return cfg


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"
