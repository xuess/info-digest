"""Tests for scripts/opml_import.py"""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.opml_import import parse_opml, import_opml


SAMPLE_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Test Subscriptions</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline type="rss" title="Hacker News" xmlUrl="https://hnrss.org/frontpage" htmlUrl="https://news.ycombinator.com"/>
      <outline type="rss" title="Tech Blog" xmlUrl="https://blog.example.com/feed" htmlUrl="https://blog.example.com"/>
    </outline>
    <outline text="AI" title="AI">
      <outline type="rss" title="AI Weekly" xmlUrl="https://ai.example.com/rss" htmlUrl="https://ai.example.com"/>
    </outline>
    <outline type="rss" title="Standalone Feed" xmlUrl="https://standalone.example.com/feed"/>
  </body>
</opml>
"""


class TestParseOpml:
    def test_parse_basic(self) -> None:
        sources = parse_opml(SAMPLE_OPML)
        assert len(sources) == 4

    def test_categories_preserved(self) -> None:
        sources = parse_opml(SAMPLE_OPML)
        tech_sources = [s for s in sources if s["category"] == "Tech"]
        ai_sources = [s for s in sources if s["category"] == "AI"]
        assert len(tech_sources) == 2
        assert len(ai_sources) == 1

    def test_urls_correct(self) -> None:
        sources = parse_opml(SAMPLE_OPML)
        urls = {s["url"] for s in sources}
        assert "https://hnrss.org/frontpage" in urls
        assert "https://ai.example.com/rss" in urls

    def test_enabled_false_by_default(self) -> None:
        sources = parse_opml(SAMPLE_OPML)
        assert all(not s["enabled"] for s in sources)

    def test_empty_opml(self) -> None:
        opml = '<?xml version="1.0"?><opml><body></body></opml>'
        assert parse_opml(opml) == []


class TestImportOpml:
    def test_import_creates_feeds_yaml(self, tmp_path: Path) -> None:
        opml_path = tmp_path / "test.opml"
        opml_path.write_text(SAMPLE_OPML)
        feeds_path = tmp_path / "feeds.yaml"

        added = import_opml(opml_path, feeds_path)
        assert added == 4

        with open(feeds_path) as f:
            data = yaml.safe_load(f)
        assert len(data["sources"]) == 4

    def test_import_merges_existing(self, tmp_path: Path) -> None:
        opml_path = tmp_path / "test.opml"
        opml_path.write_text(SAMPLE_OPML)
        feeds_path = tmp_path / "feeds.yaml"

        # Pre-existing source
        feeds_path.write_text(yaml.dump({
            "sources": [{
                "id": "hacker-news",
                "url": "https://hnrss.org/frontpage",
                "category": "tech",
                "authority": 0.9,
            }],
        }))

        added = import_opml(opml_path, feeds_path)
        assert added == 3  # HN already exists

        with open(feeds_path) as f:
            data = yaml.safe_load(f)
        assert len(data["sources"]) == 4

    def test_import_idempotent(self, tmp_path: Path) -> None:
        opml_path = tmp_path / "test.opml"
        opml_path.write_text(SAMPLE_OPML)
        feeds_path = tmp_path / "feeds.yaml"

        import_opml(opml_path, feeds_path)
        added2 = import_opml(opml_path, feeds_path)
        assert added2 == 0
