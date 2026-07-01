"""Channel protocol for delivery backends."""

from __future__ import annotations

from typing import Any, Protocol


class Channel(Protocol):
    """Protocol for delivery channels (Feishu, DingTalk, etc.)."""

    @property
    def name(self) -> str:
        """Channel name (e.g. 'feishu', 'dingtalk')."""
        ...

    def send(self, payload: str | bytes) -> bool:
        """Send a payload to the channel.

        Returns True on success, False on failure.
        Raises on permanent failure after retries.
        """
        ...
