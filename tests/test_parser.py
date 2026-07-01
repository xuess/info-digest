"""Tests for collector/parser.py"""

from __future__ import annotations

from pathlib import Path

from infodigest.collector.parser import Source, Entry, parse


def _make_source(**kwargs) -> Source:
    defaults = {
        "id": "test",
        "url": "https://example.com/feed",
        "category": "tech",
        "authority": 0.8,
        "lang": "en",
        "tags": ("test",),
        "enabled": True,
    }
    defaults.update(kwargs)
    return Source(**defaults)


class TestSource:
    def test_from_dict(self) -> None:
        d = {
            "id": "hn",
            "url": "https://hnrss.org/frontpage",
            "category": "tech",
            "authority": 0.9,
            "lang": "en",
            "tags": ["news"],
            "enabled": True,
        }
        s = Source.from_dict(d)
        assert s.id == "hn"
        assert s.authority == 0.9
        assert s.tags == ("news",)

    def test_from_dict_defaults(self) -> None:
        d = {"id": "x", "url": "https://x.com/feed"}
        s = Source.from_dict(d)
        assert s.category == ""
        assert s.authority == 0.5
        assert s.lang == ""
        assert s.tags == ()
        assert s.enabled is True


class TestParse:
    def test_parse_rss2(self, fixtures_dir: Path) -> None:
        content = (fixtures_dir / "rss2_sample.xml").read_bytes()
        source = _make_source(id="test-rss2")
        entries = parse(content, source)
        assert len(entries) == 3
        # Check first entry
        assert entries[0].title == "First Test Article"
        assert entries[0].link == "https://example.com/article-1"
        assert entries[0].source_id == "test-rss2"
        assert entries[0].published is not None
        # Summary should contain HTML
        assert "<strong>" in entries[0].summary

    def test_parse_atom(self, fixtures_dir: Path) -> None:
        content = (fixtures_dir / "atom_sample.xml").read_bytes()
        source = _make_source(id="test-atom")
        entries = parse(content, source)
        assert len(entries) == 3
        assert entries[0].title == "Atom Entry One"
        assert "Atom" in entries[0].summary or "entry" in entries[0].summary

    def test_parse_bad_feed(self, fixtures_dir: Path) -> None:
        """Bad feed should skip entries with no title/link, keep valid ones."""
        content = (fixtures_dir / "bad_feed.xml").read_bytes()
        source = _make_source(id="test-bad")
        entries = parse(content, source)
        # Only the "Valid Entry" should survive
        assert len(entries) == 1
        assert entries[0].title == "Valid Entry"

    def test_parse_empty_content(self) -> None:
        source = _make_source()
        entries = parse(b"", source)
        assert entries == []

    def test_parse_no_entries(self) -> None:
        content = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <title>Empty</title>
            <link>https://example.com</link>
        </channel></rss>"""
        source = _make_source()
        entries = parse(content, source)
        assert entries == []

    def test_parse_preserves_raw_engagement(self, fixtures_dir: Path) -> None:
        """Raw dict should preserve engagement fields if present."""
        content = (fixtures_dir / "rss2_sample.xml").read_bytes()
        source = _make_source()
        entries = parse(content, source)
        # These test fixtures don't have engagement data
        assert isinstance(entries[0].raw, dict)
