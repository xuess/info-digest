"""Normalizer — HTML cleanup, title normalization, time parsing."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from bs4 import BeautifulSoup

# Common title suffixes/prefixes to strip (e.g., " - BlogName", " | Site")
_TITLE_SUFFIX_RE = re.compile(r"\s*[-–—|]\s*[^-–—|]{2,}$")
_MULTI_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def strip_html(html: str) -> str:
    """Convert HTML to plain text, removing scripts/styles and collapsing whitespace."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    # Remove script and style elements
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    # Collapse whitespace
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text


def truncate_summary(text: str, max_len: int = 500) -> str:
    """Truncate text to max_len characters, breaking at word boundary."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Break at last space to avoid cutting words
    last_space = truncated.rfind(" ")
    if last_space > max_len * 0.8:
        truncated = truncated[:last_space]
    return truncated + "…"


def normalize_title(title: str) -> str:
    """Normalize title for deduplication: lowercase, strip suffix, fold whitespace."""
    if not title:
        return ""
    # Lowercase
    t = title.lower()
    # Strip common suffixes like " - BlogName"
    t = _TITLE_SUFFIX_RE.sub("", t)
    # Remove punctuation
    t = _PUNCT_RE.sub(" ", t)
    # Fold whitespace
    t = _MULTI_SPACE_RE.sub(" ", t).strip()
    # Unicode normalize
    t = unicodedata.normalize("NFKC", t)
    return t


def normalize_entry(
    title: str,
    summary: str,
    published: datetime | None,
    fetch_time: datetime | None = None,
) -> tuple[str, str, datetime]:
    """Normalize entry fields: clean summary, normalize title, resolve time.

    Returns (normalized_title, cleaned_summary, resolved_published).
    """
    norm_title = normalize_title(title)
    clean_summary = truncate_summary(strip_html(summary))
    resolved_time = published or fetch_time or datetime.now(timezone.utc)
    return norm_title, clean_summary, resolved_time
