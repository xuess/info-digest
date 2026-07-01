"""Tests for collector/normalizer.py"""

from __future__ import annotations

from datetime import datetime, timezone

from infodigest.collector.normalizer import (
    strip_html,
    truncate_summary,
    normalize_title,
    normalize_entry,
)


class TestStripHtml:
    def test_basic_html(self) -> None:
        html = "<p>Hello <strong>world</strong></p>"
        assert strip_html(html) == "Hello world"

    def test_script_style_removed(self) -> None:
        html = "<p>Text</p><script>alert('xss')</script><style>.x{color:red}</style>"
        result = strip_html(html)
        assert "alert" not in result
        assert "color" not in result
        assert "Text" in result

    def test_empty_string(self) -> None:
        assert strip_html("") == ""

    def test_nested_tags(self) -> None:
        html = "<div><p>A</p><p>B</p></div>"
        result = strip_html(html)
        assert "A" in result and "B" in result

    def test_entities(self) -> None:
        html = "&lt;script&gt; not tags &amp; more"
        result = strip_html(html)
        assert "<script>" in result
        assert "&" in result


class TestTruncateSummary:
    def test_short_text_unchanged(self) -> None:
        text = "Short summary"
        assert truncate_summary(text, max_len=500) == text

    def test_long_text_truncated(self) -> None:
        text = "word " * 200  # 1000 chars
        result = truncate_summary(text, max_len=500)
        assert len(result) <= 502  # +2 for "…"
        assert result.endswith("…")

    def test_breaks_at_word_boundary(self) -> None:
        text = "a" * 400 + " " + "b" * 200
        result = truncate_summary(text, max_len=500)
        assert "…" in result
        # Should not cut in middle of a repeated character run
        assert "aaa…" not in result  # Should break at space


class TestNormalizeTitle:
    def test_lowercase(self) -> None:
        assert normalize_title("Hello WORLD") == "hello world"

    def test_strip_suffix(self) -> None:
        assert normalize_title("Article Title - BlogName") == "article title"

        result = normalize_title("Article Title — SiteName")
        assert result == "article title"

    def test_strip_pipe_suffix(self) -> None:
        assert normalize_title("Article | Site") == "article"

    def test_remove_punctuation(self) -> None:
        result = normalize_title("Hello, World! (2024)")
        assert "," not in result
        assert "!" not in result

    def test_fold_whitespace(self) -> None:
        assert normalize_title("hello   world") == "hello world"

    def test_empty_string(self) -> None:
        assert normalize_title("") == ""


class TestNormalizeEntry:
    def test_normal_flow(self) -> None:
        title, summary, pub = normalize_entry(
            title="Test Article - Blog",
            summary="<p>Summary <strong>text</strong></p>",
            published=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        assert title == "test article"
        assert "Summary text" == summary
        assert pub.year == 2026

    def test_no_published_uses_fetch_time(self) -> None:
        fetch_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _, _, pub = normalize_entry(
            title="Test",
            summary="",
            published=None,
            fetch_time=fetch_time,
        )
        assert pub == fetch_time

    def test_no_published_no_fetch_uses_now(self) -> None:
        _, _, pub = normalize_entry(title="Test", summary="", published=None)
        assert pub is not None
        # Should be very recent (within a few seconds)
        now = datetime.now(timezone.utc)
        assert abs((now - pub).total_seconds()) < 5
