"""Tests for delivery channels — feishu, dingtalk, limiter, failure."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import httpx

from infodigest.delivery.base import Channel
from infodigest.delivery.feishu import FeishuChannel
from infodigest.delivery.dingtalk import DingTalkChannel
from infodigest.delivery.limiter import TokenBucketLimiter, feishu_limiter, dingtalk_limiter
from infodigest.delivery.failure import (
    save_failed_digest,
    load_pending_digests,
    remove_digest,
    increment_retry,
)


# --- Feishu tests ---

class TestFeishuChannel:
    def test_name(self) -> None:
        ch = FeishuChannel("https://example.com/webhook")
        assert ch.name == "feishu"

    def test_satisfies_protocol(self) -> None:
        ch = FeishuChannel("https://example.com/webhook")
        # Channel is a Protocol, check duck typing
        assert hasattr(ch, "send")
        assert hasattr(ch, "name")

    def test_send_invalid_json(self) -> None:
        ch = FeishuChannel("https://example.com/webhook", retries=1)
        assert ch.send("not json") is False

    def test_send_success(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="https://example.com/webhook",
            json={"code": 0, "msg": "success"},
        )
        ch = FeishuChannel("https://example.com/webhook", retries=1)
        payload = json.dumps({
            "msg_type": "interactive",
            "card": {"header": {"title": {"tag": "plain_text", "content": "Test"}}},
        })
        assert ch.send(payload) is True

    def test_send_api_error(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="https://example.com/webhook",
            json={"code": 9499, "msg": "bad"},
        )
        ch = FeishuChannel("https://example.com/webhook", retries=1)
        payload = json.dumps({"msg_type": "interactive", "card": {}})
        assert ch.send(payload) is False

    def test_send_retry_on_5xx(self, httpx_mock) -> None:
        httpx_mock.add_response(url="https://example.com/webhook", status_code=503)
        httpx_mock.add_response(
            url="https://example.com/webhook",
            json={"code": 0, "msg": "ok"},
        )
        ch = FeishuChannel("https://example.com/webhook", retries=2)
        payload = json.dumps({"msg_type": "interactive", "card": {}})
        assert ch.send(payload) is True


# --- DingTalk tests ---

class TestDingTalkChannel:
    def test_name(self) -> None:
        ch = DingTalkChannel("https://example.com/webhook")
        assert ch.name == "dingtalk"

    def test_send_success(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="https://example.com/webhook",
            json={"errcode": 0, "errmsg": "ok"},
        )
        ch = DingTalkChannel("https://example.com/webhook", retries=1)
        assert ch.send("# Hello") is True

    def test_send_api_error(self, httpx_mock) -> None:
        httpx_mock.add_response(
            url="https://example.com/webhook",
            json={"errcode": 40001, "errmsg": "invalid"},
        )
        ch = DingTalkChannel("https://example.com/webhook", retries=1)
        assert ch.send("# Hello") is False

    def test_sign_url_with_secret(self) -> None:
        ch = DingTalkChannel(
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            secret="test-secret",
        )
        url = ch._sign_url()
        assert "timestamp=" in url
        assert "sign=" in url

    def test_sign_url_no_secret(self) -> None:
        base = "https://example.com/webhook"
        ch = DingTalkChannel(base)
        assert ch._sign_url() == base


# --- Limiter tests ---

class TestTokenBucketLimiter:
    def test_acquire_within_capacity(self) -> None:
        limiter = TokenBucketLimiter(rate=10.0, max_tokens=5)
        for _ in range(5):
            assert limiter.try_acquire() is True
        assert limiter.try_acquire() is False

    def test_refill_over_time(self) -> None:
        limiter = TokenBucketLimiter(rate=100.0, max_tokens=1)
        assert limiter.try_acquire() is True
        assert limiter.try_acquire() is False
        time.sleep(0.02)  # Wait for refill
        assert limiter.try_acquire() is True

    def test_acquire_with_timeout(self) -> None:
        limiter = TokenBucketLimiter(rate=100.0, max_tokens=1)
        assert limiter.acquire(timeout=1.0) is True
        # Second acquire should wait and succeed after refill
        assert limiter.acquire(timeout=0.5) is True

    def test_acquire_timeout_exceeded(self) -> None:
        limiter = TokenBucketLimiter(rate=0.001, max_tokens=1)  # Very slow refill
        assert limiter.acquire(timeout=0.1) is True
        assert limiter.acquire(timeout=0.1) is False

    def test_feishu_limiter(self) -> None:
        limiter = feishu_limiter()
        assert isinstance(limiter, TokenBucketLimiter)
        assert limiter._max_tokens == 5

    def test_dingtalk_limiter(self) -> None:
        limiter = dingtalk_limiter()
        assert isinstance(limiter, TokenBucketLimiter)
        assert limiter._max_tokens == 20


# --- Failure persistence tests ---

class TestFailurePersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        failed_dir = tmp_path / "failed"
        digest_id = save_failed_digest(
            "feishu",
            '{"msg_type": "interactive"}',
            "connection timeout",
            failed_dir,
        )
        assert digest_id
        pending = load_pending_digests(failed_dir)
        assert len(pending) == 1
        assert pending[0]["channel"] == "feishu"
        assert pending[0]["error"] == "connection timeout"

    def test_remove_digest(self, tmp_path: Path) -> None:
        failed_dir = tmp_path / "failed"
        digest_id = save_failed_digest("feishu", "{}", "err", failed_dir)
        assert len(load_pending_digests(failed_dir)) == 1
        remove_digest(digest_id, failed_dir)
        assert len(load_pending_digests(failed_dir)) == 0

    def test_increment_retry(self, tmp_path: Path) -> None:
        failed_dir = tmp_path / "failed"
        digest_id = save_failed_digest("feishu", "{}", "err", failed_dir)
        assert increment_retry(digest_id, failed_dir) == 1
        assert increment_retry(digest_id, failed_dir) == 2

    def test_load_empty_dir(self, tmp_path: Path) -> None:
        assert load_pending_digests(tmp_path / "nonexistent") == []

    def test_save_dict_payload(self, tmp_path: Path) -> None:
        failed_dir = tmp_path / "failed"
        digest_id = save_failed_digest(
            "dingtalk",
            {"msgtype": "markdown", "markdown": {"text": "test"}},
            "error",
            failed_dir,
        )
        pending = load_pending_digests(failed_dir)
        assert len(pending) == 1
