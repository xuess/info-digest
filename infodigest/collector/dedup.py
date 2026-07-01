"""Deduplication — sha1 primary key + title Jaccard similarity."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from infodigest.collector.parser import Entry
from infodigest.collector.normalizer import normalize_title


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _title_words(title: str) -> set[str]:
    """Extract word set from a normalized title for Jaccard computation."""
    return set(_WORD_RE.findall(title.lower()))


def compute_uid(title: str, link: str) -> str:
    """Compute unique ID: sha1(normalized_title + source_domain)."""
    domain = ""
    if link:
        try:
            domain = urlparse(link).netloc
        except Exception:
            pass
    norm = normalize_title(title)
    payload = f"{norm}|{domain}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def jaccard_similarity(words_a: set[str], words_b: set[str]) -> float:
    """Compute Jaccard similarity between two word sets."""
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def is_duplicate(
    title: str,
    recent_titles: list[str],
    threshold: float = 0.8,
) -> bool:
    """Check if title is a duplicate of any recent title using Jaccard similarity."""
    words = _title_words(normalize_title(title))
    for recent in recent_titles:
        recent_words = _title_words(recent)
        if jaccard_similarity(words, recent_words) >= threshold:
            return True
    return False


def assign_uids(entries: list[Entry]) -> list[Entry]:
    """Assign UIDs to entries. Returns new Entry objects with uid set."""
    result: list[Entry] = []
    for e in entries:
        uid = compute_uid(e.title, e.link)
        result.append(Entry(
            uid=uid,
            source_id=e.source_id,
            title=e.title,
            summary=e.summary,
            link=e.link,
            published=e.published,
            raw=e.raw,
        ))
    return result


def dedup_entries(
    entries: list[Entry],
    recent_titles: list[str] | None = None,
    threshold: float = 0.8,
) -> list[Entry]:
    """Deduplicate entries by UID (exact) and title similarity (Jaccard).

    Returns entries with UIDs assigned, duplicates removed.
    """
    if recent_titles is None:
        recent_titles = []

    # First pass: assign UIDs
    entries = assign_uids(entries)

    # Second pass: exact UID dedup (keep first occurrence)
    seen_uids: set[str] = set()
    uid_deduped: list[Entry] = []
    for e in entries:
        if e.uid not in seen_uids:
            seen_uids.add(e.uid)
            uid_deduped.append(e)

    # Third pass: Jaccard similarity dedup against recent titles
    result: list[Entry] = []
    all_norm_titles = list(recent_titles)
    for e in uid_deduped:
        norm = normalize_title(e.title)
        if not is_duplicate(norm, all_norm_titles, threshold):
            result.append(e)
            all_norm_titles.append(norm)

    return result
