"""Tests for collector/dedup.py"""

from __future__ import annotations

from datetime import datetime, timezone

from infodigest.collector.dedup import (
    compute_uid,
    jaccard_similarity,
    is_duplicate,
    assign_uids,
    dedup_entries,
)
from infodigest.collector.parser import Entry


def _make_entry(title: str, link: str = "https://example.com/art", source_id: str = "test") -> Entry:
    return Entry(
        uid="",
        source_id=source_id,
        title=title,
        summary="",
        link=link,
        published=datetime(2026, 6, 30, tzinfo=timezone.utc),
        raw={},
    )


class TestComputeUid:
    def test_deterministic(self) -> None:
        uid1 = compute_uid("Hello World", "https://example.com/a")
        uid2 = compute_uid("Hello World", "https://example.com/a")
        assert uid1 == uid2

    def test_different_title_different_uid(self) -> None:
        uid1 = compute_uid("Article A", "https://example.com/a")
        uid2 = compute_uid("Article B", "https://example.com/a")
        assert uid1 != uid2

    def test_different_domain_different_uid(self) -> None:
        uid1 = compute_uid("Same Title", "https://a.com/x")
        uid2 = compute_uid("Same Title", "https://b.com/x")
        assert uid1 != uid2

    def test_empty_link(self) -> None:
        uid = compute_uid("Title", "")
        assert len(uid) == 40  # SHA1 hex length


class TestJaccardSimilarity:
    def test_identical(self) -> None:
        words = {"hello", "world"}
        assert jaccard_similarity(words, words) == 1.0

    def test_disjoint(self) -> None:
        assert jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self) -> None:
        a = {"a", "b", "c"}
        b = {"b", "c", "d"}
        # intersection={b,c}=2, union={a,b,c,d}=4 → 0.5
        assert jaccard_similarity(a, b) == 0.5

    def test_both_empty(self) -> None:
        assert jaccard_similarity(set(), set()) == 1.0

    def test_one_empty(self) -> None:
        assert jaccard_similarity({"a"}, set()) == 0.0


class TestIsDuplicate:
    def test_exact_match(self) -> None:
        recent = ["hello world"]
        assert is_duplicate("Hello World", recent, threshold=0.8) is True

    def test_similar_above_threshold(self) -> None:
        recent = ["new ai model released today"]
        # "new ai model released today" vs "new ai model released now"
        # intersection: {new, ai, model, released}=4, union: {new, ai, model, released, today, now}=6
        # jaccard = 4/6 ≈ 0.667 — below 0.8
        assert is_duplicate("New AI model released now", recent, threshold=0.8) is False

    def test_below_threshold(self) -> None:
        recent = ["completely different article about cooking"]
        assert is_duplicate("New AI model released", recent, threshold=0.8) is False

    def test_empty_recent(self) -> None:
        assert is_duplicate("Title", [], threshold=0.8) is False


class TestAssignUids:
    def test_assigns_uids(self) -> None:
        entries = [_make_entry("A"), _make_entry("B")]
        result = assign_uids(entries)
        assert all(e.uid != "" for e in result)
        assert result[0].uid != result[1].uid

    def test_preserves_fields(self) -> None:
        entry = _make_entry("Test", "https://example.com/test")
        result = assign_uids([entry])
        assert result[0].title == "Test"
        assert result[0].source_id == "test"


class TestDedupEntries:
    def test_exact_uid_dedup(self) -> None:
        """Same title+link should be deduplicated by UID."""
        entries = [
            _make_entry("Same Article", "https://example.com/a"),
            _make_entry("Same Article", "https://example.com/a"),
        ]
        result = dedup_entries(entries)
        assert len(result) == 1

    def test_different_entries_kept(self) -> None:
        entries = [
            _make_entry("Article A", "https://example.com/a"),
            _make_entry("Article B", "https://example.com/b"),
        ]
        result = dedup_entries(entries)
        assert len(result) == 2

    def test_jaccard_dedup_against_recent(self) -> None:
        """Entry similar to recent title should be filtered."""
        entries = [_make_entry("Hello World")]
        recent = ["hello world"]
        result = dedup_entries(entries, recent_titles=recent, threshold=0.8)
        assert len(result) == 0

    def test_empty_input(self) -> None:
        assert dedup_entries([]) == []
