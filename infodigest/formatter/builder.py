"""Jinja2 formatter — builds digest payloads without LLM."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from infodigest.rater.scorer import ScoredEntry


@dataclass(frozen=True)
class DigestChunk:
    """A chunk of digest entries that fits within size limits."""
    entries: list[ScoredEntry]
    index: int  # 0-based chunk index
    total_chunks: int


def _get_jinja_env(template_dir: str | Path = "config/templates") -> Environment:
    """Create Jinja2 environment with template directory."""
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_feishu_card(
    entries: list[ScoredEntry],
    template_dir: str | Path = "config/templates",
) -> dict[str, Any]:
    """Build a Feishu interactive card JSON from scored entries."""
    env = _get_jinja_env(template_dir)
    template = env.get_template("feishu_card.j2")
    rendered = template.render(entries=entries, now=datetime.now(timezone.utc))
    return json.loads(rendered)


def build_dingtalk_md(
    entries: list[ScoredEntry],
    template_dir: str | Path = "config/templates",
) -> str:
    """Build a DingTalk markdown message from scored entries."""
    env = _get_jinja_env(template_dir)
    template = env.get_template("dingtalk_md.j2")
    return template.render(entries=entries, now=datetime.now(timezone.utc))


def build_digest_section(
    entries: list[ScoredEntry],
    template_dir: str | Path = "config/templates",
) -> str:
    """Build a digest section (reusable block) from scored entries."""
    env = _get_jinja_env(template_dir)
    template = env.get_template("digest_section.j2")
    return template.render(entries=entries)


def chunk_entries(
    entries: list[ScoredEntry],
    max_entries: int = 20,
    max_bytes: int = 30000,
) -> list[DigestChunk]:
    """Split entries into chunks respecting count and byte limits.

    Args:
        entries: Scored entries to chunk.
        max_entries: Max entries per chunk.
        max_bytes: Max byte size per chunk (approximate, via JSON encoding).

    Returns:
        List of DigestChunk objects.
    """
    if not entries:
        return []

    chunks: list[DigestChunk] = []
    current: list[ScoredEntry] = []
    current_bytes = 0

    for entry in entries:
        # Estimate size of this entry
        entry_bytes = len(json.dumps({
            "title": entry.title,
            "summary": entry.summary,
            "link": entry.link,
        }).encode("utf-8"))

        # Check if adding this entry would exceed limits
        if current and (
            len(current) >= max_entries
            or current_bytes + entry_bytes > max_bytes
        ):
            chunks.append(DigestChunk(
                entries=list(current),
                index=len(chunks),
                total_chunks=0,  # Filled below
            ))
            current = []
            current_bytes = 0

        current.append(entry)
        current_bytes += entry_bytes

    # Don't forget the last chunk
    if current:
        chunks.append(DigestChunk(
            entries=list(current),
            index=len(chunks),
            total_chunks=0,
        ))

    # Fill total_chunks
    total = len(chunks)
    chunks = [
        DigestChunk(
            entries=ch.entries,
            index=ch.index,
            total_chunks=total,
        )
        for ch in chunks
    ]

    return chunks
