"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

from infodigest.config import load_config


def test_load_config_defaults(config_dir: Path) -> None:
    cfg = load_config(config_dir)
    assert cfg.storage.db_path == "data/test.db"
    assert cfg.collector.timeout == 10
    assert cfg.collector.retries == 1
    assert cfg.delivery.feishu.enabled is False
    assert cfg.delivery.dingtalk.enabled is False
    assert cfg.config_dir == config_dir


def test_load_config_real() -> None:
    """Test loading from actual config directory."""
    cfg = load_config("config")
    assert cfg.storage.db_path == "data/infodigest.db"
    assert cfg.collector.timeout == 15
    assert cfg.delivery.feishu.enabled is True
    assert cfg.delivery.feishu.webhook_env == "FEISHU_WEBHOOK"


def test_delivery_channel_webhook_from_env(monkeypatch, config_dir: Path) -> None:
    cfg = load_config(config_dir)
    # Feishu is disabled in test config, webhook should be empty
    assert cfg.delivery.feishu.webhook_url == ""
    assert cfg.delivery.feishu.secret == ""
