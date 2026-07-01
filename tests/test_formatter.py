"""Tests for formatter/builder.py"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from infodigest.formatter.builder import (
    build_feishu_card,
    build_dingtalk_md,
    build_digest_section,
    chunk_entries,
    DigestChunk,
)
from infodigest.rater.scorer import ScoredEntry


def _make_scored(
    title: str = "Test Article",
    summary: str = "Test summary",
    link: str = "https://example.com/a",
    score: float = 80.0,
    grade: str = "A",
) -> ScoredEntry:
    return ScoredEntry(
        uid="abc",
        source_id="test",
        title=title,
        summary=summary,
        link=link,
        published=datetime(2026, 6, 30, tzinfo=timezone.utc),
        raw={},
        raw_score=score,
        grade=grade,
    )


@pytest.fixture
def template_dir() -> Path:
    return Path("config/templates")


class TestBuildFeishuCard:
    def test_basic_card(self, template_dir: Path) -> None:
        entries = [_make_scored("AI News", "Great AI article")]
        card = build_feishu_card(entries, template_dir)
        assert card["msg_type"] == "interactive"
        assert "card" in card
        assert "elements" in card["card"]
        assert len(card["card"]["elements"]) >= 1

    def test_multiple_entries(self, template_dir: Path) -> None:
        entries = [
            _make_scored(f"Article {i}", f"Summary {i}")
            for i in range(3)
        ]
        card = build_feishu_card(entries, template_dir)
        # Each entry produces a div + hr separator
        elements = card["card"]["elements"]
        assert len(elements) >= 3  # divs

    def test_empty_entries(self, template_dir: Path) -> None:
        card = build_feishu_card([], template_dir)
        assert card["msg_type"] == "interactive"


class TestBuildDingtalkMd:
    def test_basic_md(self, template_dir: Path) -> None:
        entries = [_make_scored("AI News", "Great article")]
        md = build_dingtalk_md(entries, template_dir)
        assert "AI News" in md
        assert "InfoDigest" in md

    def test_multiple_entries(self, template_dir: Path) -> None:
        entries = [_make_scored(f"Article {i}") for i in range(3)]
        md = build_dingtalk_md(entries, template_dir)
        for i in range(3):
            assert f"Article {i}" in md


class TestBuildDigestSection:
    def test_section(self, template_dir: Path) -> None:
        entries = [_make_scored("Test", "Summary")]
        section = build_digest_section(entries, template_dir)
        assert "Test" in section
        assert "A" in section


class TestChunkEntries:
    def test_no_chunking_needed(self) -> None:
        entries = [_make_scored(f"Art {i}") for i in range(5)]
        chunks = chunk_entries(entries, max_entries=20, max_bytes=30000)
        assert len(chunks) == 1
        assert chunks[0].total_chunks == 1
        assert len(chunks[0].entries) == 5

    def test_chunk_by_count(self) -> None:
        entries = [_make_scored(f"Art {i}") for i in range(25)]
        chunks = chunk_entries(entries, max_entries=10, max_bytes=300000)
        assert len(chunks) == 3
        assert len(chunks[0].entries) == 10
        assert len(chunks[1].entries) == 10
        assert len(chunks[2].entries) == 5

    def test_chunk_by_bytes(self) -> None:
        # Create entries with long summaries to trigger byte limit
        entries = [
            _make_scored(f"Art {i}", summary="x" * 5000)
            for i in range(10)
        ]
        chunks = chunk_entries(entries, max_entries=100, max_bytes=15000)
        assert len(chunks) > 1

    def test_empty_entries(self) -> None:
        assert chunk_entries([]) == []

    def test_chunk_metadata(self) -> None:
        entries = [_make_scored(f"Art {i}") for i in range(15)]
        chunks = chunk_entries(entries, max_entries=5)
        assert len(chunks) == 3
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
            assert chunk.total_chunks == 3

    def test_single_large_entry(self) -> None:
        """A single entry exceeding byte limit should still be in its own chunk."""
        entries = [_make_scored("Big", summary="x" * 100000)]
        chunks = chunk_entries(entries, max_entries=100, max_bytes=1000)
        assert len(chunks) == 1
        assert chunks[0].entries[0].title == "Big"
