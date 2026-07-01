"""Feishu (Lark) delivery channel — interactive card webhook."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FeishuChannel:
    """Feishu custom bot webhook delivery."""

    def __init__(
        self,
        webhook_url: str,
        timeout: int = 15,
        retries: int = 3,
    ) -> None:
        self._webhook_url = webhook_url
        self._timeout = timeout
        self._retries = retries

    @property
    def name(self) -> str:
        return "feishu"

    def send(self, payload: str | bytes) -> bool:
        """Send an interactive card to Feishu webhook.

        payload: JSON string of the card (from feishu_card.j2 template).
        Returns True on success.
        """
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        # Validate JSON
        try:
            card_data = json.loads(payload)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON payload for Feishu: %s", exc)
            return False

        last_exc: Exception | None = None
        for attempt in range(self._retries):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(
                        self._webhook_url,
                        json=card_data,
                        headers={"Content-Type": "application/json"},
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    if result.get("code") == 0 or result.get("StatusCode") == 0:
                        logger.info("Feishu message sent successfully")
                        return True
                    else:
                        logger.warning("Feishu API error: %s", result)
                        last_exc = Exception(f"Feishu API error: {result}")
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    logger.warning("Feishu rate limited, waiting 12s")
                    time.sleep(12)
                    continue
                last_exc = exc
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc

            wait = 2 ** attempt
            logger.info("Feishu retry %d/%d in %ds", attempt + 1, self._retries, wait)
            time.sleep(wait)

        logger.error("Feishu delivery failed after %d retries: %s", self._retries, last_exc)
        return False
