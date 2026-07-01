"""Feed parser — normalizes RSS/Atom/RDF entries into Entry dataclass."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from time import mktime
from typing import Any

import feedparser

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    """Represents a feed source from the registry."""
    id: str
    url: str
    category: str
    authority: float
    lang: str
    tags: tuple[str, ...]
    enabled: bool = True
    parser_hint: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Source:
        return cls(
            id=d["id"],
            url=d["url"],
            category=d.get("category", ""),
            authority=d.get("authority", 0.5),
            lang=d.get("lang", ""),
            tags=tuple(d.get("tags", [])),
            enabled=d.get("enabled", True),
            parser_hint=d.get("parser", ""),
        )


@dataclass(frozen=True)
class Entry:
    """A normalized feed entry."""
    uid: str  # Will be set by dedup; empty string until then
    source_id: str
    title: str
    summary: str
    link: str
    published: datetime | None
    raw: dict[str, Any]  # Original feedparser entry for engagement data etc.


def _parse_published(entry: dict[str, Any]) -> datetime | None:
    """Extract published datetime from feedparser entry."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    return None


def _extract_summary(entry: dict[str, Any]) -> str:
    """Extract summary text from feedparser entry, trying multiple fields."""
    summary = entry.get("summary", "")
    if not summary:
        content = entry.get("content", [])
        if content and isinstance(content, list):
            summary = content[0].get("value", "")
    return summary or ""


def parse(content: bytes, source: Source) -> list[Entry]:
    """Parse feed content into a list of Entry objects.

    Handles RSS 2.0, Atom 1.0, and RDF (RSS 1.0).
    Skips entries with no title or no link.
    """
    feed = feedparser.parse(content)

    if feed.bozo and not feed.entries:
        logger.warning("Feed parse error for %s: %s", source.id, feed.bozo_exception)
        return []

    entries: list[Entry] = []
    now = datetime.now(timezone.utc)

    for fe in feed.entries:
        title = (fe.get("title") or "").strip()
        link = (fe.get("link") or "").strip()

        if not title or not link:
            logger.debug("Skipping entry with missing title/link in %s", source.id)
            continue

        summary = _extract_summary(fe)
        published = _parse_published(fe) or now

        # Build raw dict with engagement-relevant fields
        raw: dict[str, Any] = {}
        for key in ("comments", "comments_count", "points", "score"):
            if key in fe:
                raw[key] = fe[key]

        entries.append(Entry(
            uid="",  # Will be set by dedup
            source_id=source.id,
            title=title,
            summary=summary,
            link=link,
            published=published,
            raw=raw,
        ))

    logger.info("Parsed %d entries from %s", len(entries), source.id)
    return entries
