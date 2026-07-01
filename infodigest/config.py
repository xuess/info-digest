"""Configuration loading from YAML files."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CollectorConfig:
    timeout: int = 15
    retries: int = 3
    user_agent: str = "InfoDigest/1.0"


@dataclass(frozen=True)
class DeliveryChannelConfig:
    enabled: bool = False
    webhook_env: str = ""
    secret_env: str = ""

    @property
    def webhook_url(self) -> str:
        return os.environ.get(self.webhook_env, "")

    @property
    def secret(self) -> str:
        return os.environ.get(self.secret_env, "")


@dataclass(frozen=True)
class DeliveryConfig:
    feishu: DeliveryChannelConfig = field(default_factory=DeliveryChannelConfig)
    dingtalk: DeliveryChannelConfig = field(default_factory=DeliveryChannelConfig)


@dataclass(frozen=True)
class StorageConfig:
    db_path: str = "data/infodigest.db"
    failed_digests_dir: str = "data/failed_digests"


@dataclass(frozen=True)
class SchedulerConfig:
    cron: str = "0 1,9 * * *"


@dataclass(frozen=True)
class Config:
    storage: StorageConfig = field(default_factory=StorageConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    delivery: DeliveryConfig = field(default_factory=DeliveryConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    config_dir: Path = field(default_factory=lambda: Path("config"))


def _build_delivery(raw: dict[str, Any]) -> DeliveryConfig:
    feishu_raw = raw.get("feishu", {})
    dingtalk_raw = raw.get("dingtalk", {})
    return DeliveryConfig(
        feishu=DeliveryChannelConfig(
            enabled=feishu_raw.get("enabled", False),
            webhook_env=feishu_raw.get("webhook_env", "FEISHU_WEBHOOK"),
            secret_env=feishu_raw.get("secret_env", "FEISHU_SECRET"),
        ),
        dingtalk=DeliveryChannelConfig(
            enabled=dingtalk_raw.get("enabled", False),
            webhook_env=dingtalk_raw.get("webhook_env", "DINGTALK_WEBHOOK"),
            secret_env=dingtalk_raw.get("secret_env", "DINGTALK_SECRET"),
        ),
    )


def load_config(config_dir: str | Path = "config") -> Config:
    """Load configuration from YAML files in config_dir."""
    config_dir = Path(config_dir)
    settings_path = config_dir / "settings.yaml"

    with open(settings_path) as f:
        raw = yaml.safe_load(f) or {}

    storage_raw = raw.get("storage", {})
    collector_raw = raw.get("collector", {})
    scheduler_raw = raw.get("scheduler", {})

    return Config(
        storage=StorageConfig(
            db_path=storage_raw.get("db_path", "data/infodigest.db"),
            failed_digests_dir=storage_raw.get("failed_digests_dir", "data/failed_digests"),
        ),
        collector=CollectorConfig(
            timeout=collector_raw.get("timeout", 15),
            retries=collector_raw.get("retries", 3),
            user_agent=collector_raw.get("user_agent", "InfoDigest/1.0"),
        ),
        delivery=_build_delivery(raw.get("delivery", {})),
        scheduler=SchedulerConfig(
            cron=scheduler_raw.get("cron", "0 1,9 * * *"),
        ),
        config_dir=config_dir,
    )
