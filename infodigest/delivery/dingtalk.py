"""DingTalk delivery channel — markdown + HMAC signature."""

from __future__ import annotations

import hashlib
import hmac
import base64
import json
import logging
import time
import urllib.parse
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DingTalkChannel:
    """DingTalk custom bot webhook delivery with HMAC signing."""

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        timeout: int = 15,
        retries: int = 3,
    ) -> None:
        self._webhook_url = webhook_url
        self._secret = secret
        self._timeout = timeout
        self._retries = retries

    @property
    def name(self) -> str:
        return "dingtalk"

    def _sign_url(self) -> str:
        """Build signed webhook URL with timestamp + HMAC-SHA256."""
        if not self._secret:
            return self._webhook_url

        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))

        sep = "&" if "?" in self._webhook_url else "?"
        return f"{self._webhook_url}{sep}timestamp={timestamp}&sign={sign}"

    def send(self, payload: str | bytes) -> bool:
        """Send a markdown message to DingTalk webhook.

        payload: markdown text (from dingtalk_md.j2 template).
        Returns True on success.
        """
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        url = self._sign_url()
        body = {
            "msgtype": "markdown",
            "markdown": {
                "title": "InfoDigest 每日精选",
                "text": payload,
            },
        }

        last_exc: Exception | None = None
        for attempt in range(self._retries):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(
                        url,
                        json=body,
                        headers={"Content-Type": "application/json"},
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    if result.get("errcode") == 0:
                        logger.info("DingTalk message sent successfully")
                        return True
                    else:
                        logger.warning("DingTalk API error: %s", result)
                        last_exc = Exception(f"DingTalk API error: {result}")
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    logger.warning("DingTalk rate limited, waiting 3s")
                    time.sleep(3)
                    continue
                last_exc = exc
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc

            wait = 2 ** attempt
            logger.info("DingTalk retry %d/%d in %ds", attempt + 1, self._retries, wait)
            time.sleep(wait)

        logger.error("DingTalk delivery failed after %d retries: %s", self._retries, last_exc)
        return False
