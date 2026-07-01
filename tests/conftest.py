"""Shared test fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from infodigest.config import Config, StorageConfig, CollectorConfig, DeliveryConfig, DeliveryChannelConfig, SchedulerConfig


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
def full_config(tmp_path: Path) -> Config:
    """Create a minimal but complete config for pipeline testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    templates_dir = config_dir / "templates"
    templates_dir.mkdir()

    (config_dir / "settings.yaml").write_text(
        "storage:\n"
        f"  db_path: {tmp_path}/data/test.db\n"
        f"  failed_digests_dir: {tmp_path}/data/failed\n"
        "collector:\n"
        "  timeout: 5\n"
        "  retries: 1\n"
        "  user_agent: TestDigest/1.0\n"
        "delivery:\n"
        "  feishu:\n"
        "    enabled: false\n"
        "  dingtalk:\n"
        "    enabled: false\n"
    )
    (config_dir / "feeds.yaml").write_text(yaml.dump({
        "sources": [{
            "id": "test-feed",
            "url": "https://example.com/feed.xml",
            "category": "tech",
            "authority": 0.8,
            "lang": "en",
            "tags": ["test"],
            "enabled": True,
        }],
    }))
    (config_dir / "rater.yaml").write_text(yaml.dump({
        "weights": {"authority": 30, "freshness": 25, "relevance": 25,
                    "uniqueness": 10, "engagement": 10},
        "freshness_half_life_hours": 72,
        "max_age_hours": 168,
        "relevance_target": 3.0,
        "engagement_threshold": 200,
        "grade_thresholds": {"A": 75, "B": 50},
        "push_grade_min": "B",
        "keywords": {},
        "dedup_similarity": 0.8,
        "dedup_window_days": 7,
    }))
    (templates_dir / "feishu_card.j2").write_text(
        '{"msg_type":"interactive","card":{"elements":[]}}'
    )
    (templates_dir / "dingtalk_md.j2").write_text("# Digest\nNo entries.")
    (templates_dir / "digest_section.j2").write_text("No entries.")

    return Config(
        storage=StorageConfig(
            db_path=str(tmp_path / "data" / "test.db"),
            failed_digests_dir=str(tmp_path / "data" / "failed"),
        ),
        collector=CollectorConfig(timeout=5, retries=1),
        delivery=DeliveryConfig(
            feishu=DeliveryChannelConfig(enabled=False),
            dingtalk=DeliveryChannelConfig(enabled=False),
        ),
        scheduler=SchedulerConfig(),
        config_dir=config_dir,
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"
