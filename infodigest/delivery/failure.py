"""Failed digest persistence and retry."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def save_failed_digest(
    channel: str,
    payload: str | dict[str, Any],
    error: str,
    failed_dir: str | Path = "data/failed_digests",
) -> str:
    """Save a failed digest payload to disk for later retry.

    Returns the digest ID.
    """
    failed_dir = Path(failed_dir)
    failed_dir.mkdir(parents=True, exist_ok=True)

    digest_id = uuid.uuid4().hex[:16]
    data = {
        "id": digest_id,
        "channel": channel,
        "payload": payload if isinstance(payload, str) else json.dumps(payload),
        "error": error,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "retries": 0,
    }

    path = failed_dir / f"{digest_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info("Saved failed digest %s for channel %s", digest_id, channel)
    return digest_id


def load_pending_digests(
    failed_dir: str | Path = "data/failed_digests",
) -> list[dict[str, Any]]:
    """Load all pending failed digests for retry."""
    failed_dir = Path(failed_dir)
    if not failed_dir.exists():
        return []

    digests: list[dict[str, Any]] = []
    for path in sorted(failed_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            data["_path"] = str(path)
            digests.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load digest %s: %s", path, exc)

    return digests


def remove_digest(digest_id: str, failed_dir: str | Path = "data/failed_digests") -> None:
    """Remove a successfully retried digest from disk."""
    path = Path(failed_dir) / f"{digest_id}.json"
    if path.exists():
        path.unlink()
        logger.info("Removed retried digest %s", digest_id)


def increment_retry(
    digest_id: str,
    failed_dir: str | Path = "data/failed_digests",
) -> int:
    """Increment retry count for a failed digest. Returns new count."""
    path = Path(failed_dir) / f"{digest_id}.json"
    if not path.exists():
        return 0

    data = json.loads(path.read_text())
    data["retries"] = data.get("retries", 0) + 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data["retries"]
