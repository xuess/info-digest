"""Tests for rater/scorer.py — five-dimension scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from infodigest.collector.parser import Entry
from infodigest.rater.scorer import (
    RaterConfig,
    ScoreContext,
    ScoredEntry,
    _freshness_score,
    _relevance_score,
    _uniqueness_score,
    _engagement_score,
    _grade,
    score,
)


def _make_entry(
    title: str = "Test Article",
    summary: str = "Summary",
    link: str = "https://example.com/a",
    published: datetime | None = None,
    raw: dict | None = None,
) -> Entry:
    return Entry(
        uid="abc123",
        source_id="test",
        title=title,
        summary=summary,
        link=link,
        published=published,
        raw=raw or {},
    )


def _default_config(**overrides) -> RaterConfig:
    defaults = {
        "weights": {"authority": 30, "freshness": 25, "relevance": 25,
                     "uniqueness": 10, "engagement": 10},
        "freshness_half_life_hours": 72,
        "max_age_hours": 168,
        "relevance_target": 3.0,
        "engagement_threshold": 200,
        "grade_thresholds": {"A": 75, "B": 50},
        "push_grade_min": "B",
        "keywords": {"ai": 1.0, "llm": 1.0, "rust": 0.7},
        "dedup_similarity": 0.8,
        "dedup_window_days": 7,
    }
    defaults.update(overrides)
    return RaterConfig.from_dict(defaults)


def _make_ctx(
    config: RaterConfig | None = None,
    source_authority: float = 0.8,
    recent_titles: list[str] | None = None,
) -> ScoreContext:
    return ScoreContext(
        config=config or _default_config(),
        source_authority=source_authority,
        recent_titles=recent_titles or [],
    )


class TestFreshnessScore:
    def test_very_fresh(self) -> None:
        now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
        published = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
        assert _freshness_score(published, 72, 168, now) == 1.0

    def test_half_life(self) -> None:
        now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
        published = now - timedelta(hours=72)
        score = _freshness_score(published, 72, 168, now)
        assert abs(score - 0.3679) < 0.01  # exp(-1) ≈ 0.3679

    def test_very_old(self) -> None:
        now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
        published = now - timedelta(hours=200)  # > 168h max
        assert _freshness_score(published, 72, 168, now) == 0.0

    def test_no_published(self) -> None:
        assert _freshness_score(None, 72, 168) == 1.0

    def test_future_date(self) -> None:
        now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
        published = now + timedelta(hours=1)
        assert _freshness_score(published, 72, 168, now) == 1.0


class TestRelevanceScore:
    def test_no_keywords_neutral(self) -> None:
        assert _relevance_score("title", "summary", {}, 3.0) == 0.5

    def test_title_hit(self) -> None:
        keywords = {"ai": 1.0}
        result = _relevance_score("New AI model released", "", keywords, 3.0)
        assert result == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_summary_hit_lower_weight(self) -> None:
        keywords = {"ai": 1.0}
        # Title hit = 1.0 * 1.0, summary hit = 1.0 * 0.4 → total 1.4 / 3.0
        result = _relevance_score("AI news", "This is about ai technology", keywords, 3.0)
        assert result == pytest.approx(1.4 / 3.0, abs=0.01)

    def test_full_relevance(self) -> None:
        keywords = {"ai": 1.0, "llm": 1.0, "rust": 1.0}
        result = _relevance_score("AI LLM Rust", "ai llm rust content", keywords, 3.0)
        # title: 3*1.0 = 3.0, summary: 3*0.4 = 1.2 → total 4.2, clamp to 1.0
        assert result == 1.0

    def test_no_match(self) -> None:
        keywords = {"ai": 1.0}
        result = _relevance_score("Cooking recipes", "Food guide", keywords, 3.0)
        assert result == 0.0

    def test_html_in_summary(self) -> None:
        keywords = {"ai": 1.0}
        result = _relevance_score("Tech", "<p>New AI breakthrough</p>", keywords, 3.0)
        assert result > 0


class TestUniquenessScore:
    def test_no_recent(self) -> None:
        assert _uniqueness_score("Any title", []) == 1.0

    def test_identical_recent(self) -> None:
        assert _uniqueness_score("hello world", ["hello world"]) == 0.0

    def test_different_recent(self) -> None:
        result = _uniqueness_score("completely different", ["hello world"])
        assert result > 0.9

    def test_similar_recent(self) -> None:
        result = _uniqueness_score("new ai model", ["new ai model released today"])
        assert 0.0 < result < 1.0


class TestEngagementScore:
    def test_no_engagement(self) -> None:
        assert _engagement_score({}, 200) == 0.0

    def test_points(self) -> None:
        assert _engagement_score({"points": 100}, 200) == 0.5

    def test_full_engagement(self) -> None:
        assert _engagement_score({"points": 500}, 200) == 1.0

    def test_comments(self) -> None:
        assert _engagement_score({"comments_count": 50}, 200) == 0.25

    def test_string_value(self) -> None:
        assert _engagement_score({"points": "150"}, 200) == 0.75


class TestGrade:
    def test_grade_a(self) -> None:
        assert _grade(80, {"A": 75, "B": 50}) == "A"

    def test_grade_b(self) -> None:
        assert _grade(60, {"A": 75, "B": 50}) == "B"

    def test_grade_c(self) -> None:
        assert _grade(30, {"A": 75, "B": 50}) == "C"

    def test_boundary_a(self) -> None:
        assert _grade(75, {"A": 75, "B": 50}) == "A"

    def test_boundary_b(self) -> None:
        assert _grade(50, {"A": 75, "B": 50}) == "B"


class TestScore:
    def test_score_returns_scored_entry(self) -> None:
        ctx = _make_ctx()
        entry = _make_entry()
        result = score(entry, ctx)
        assert isinstance(result, ScoredEntry)
        assert 0 <= result.raw_score <= 100
        assert result.grade in ("A", "B", "C")

    def test_score_preserves_fields(self) -> None:
        ctx = _make_ctx()
        entry = _make_entry(title="My Title", link="https://example.com/x")
        result = score(entry, ctx)
        assert result.title == "My Title"
        assert result.link == "https://example.com/x"
        assert result.uid == "abc123"

    def test_high_authority_high_score(self) -> None:
        """High authority + fresh + relevant keywords → high score."""
        cfg = _default_config(
            keywords={"ai": 1.0, "llm": 1.0},
            relevance_target=2.0,
        )
        ctx = _make_ctx(config=cfg, source_authority=1.0)
        entry = _make_entry(
            title="New AI LLM breakthrough",
            published=datetime.now(timezone.utc),
        )
        result = score(entry, ctx)
        assert result.raw_score >= 60  # Should be reasonably high

    def test_very_old_low_score(self) -> None:
        """Very old entry should score low due to freshness=0."""
        ctx = _make_ctx(source_authority=1.0)
        entry = _make_entry(
            published=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        result = score(entry, ctx)
        assert result.raw_score < 50  # freshness=0 drags it down

    def test_score_range_0_100(self) -> None:
        """Score should always be in [0, 100]."""
        cfg = _default_config()
        ctx = _make_ctx(config=cfg, source_authority=1.0)
        for i in range(20):
            entry = _make_entry(
                title=f"Article {i} with ai keyword",
                published=datetime.now(timezone.utc) - timedelta(hours=i * 10),
                raw={"points": i * 50},
            )
            result = score(entry, ctx)
            assert 0 <= result.raw_score <= 100, f"Score {result.raw_score} out of range"

    def test_pure_function_no_side_effects(self) -> None:
        """Scoring twice gives same result (pure function)."""
        ctx = _make_ctx()
        entry = _make_entry(title="AI article", published=datetime.now(timezone.utc))
        r1 = score(entry, ctx)
        r2 = score(entry, ctx)
        assert r1.raw_score == r2.raw_score
        assert r1.grade == r2.grade


class TestOfflineRegression:
    """Regression fixtures: given fixed entries, assert stable scores and grades."""

    def test_regression_five_entries(self) -> None:
        """Given 5 fixed entries, scores and grades should be stable."""
        cfg = _default_config(
            keywords={"ai": 1.0, "llm": 1.0, "rust": 0.7, "开源": 0.6},
            relevance_target=3.0,
        )
        now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)

        entries_data = [
            # (title, summary, authority, hours_ago, points, expected_grade_min)
            ("New AI LLM model released", "A major ai breakthrough", 0.9, 2, 100, "A"),
            ("Rust memory safety update", "Rust language update", 0.8, 12, 0, "B"),
            ("Random cooking blog post", "Recipes and food", 0.3, 48, 0, "C"),
            ("开源项目发布新版本", "开源社区动态", 0.7, 6, 0, "B"),
            ("Old tech news from last week", "Something old", 0.9, 160, 50, "C"),
        ]

        for title, summary, authority, hours_ago, points, grade_min in entries_data:
            ctx = _make_ctx(config=cfg, source_authority=authority)
            entry = _make_entry(
                title=title,
                summary=summary,
                published=now - timedelta(hours=hours_ago),
                raw={"points": points} if points else {},
            )
            result = score(entry, ctx)

            # Verify score is in range
            assert 0 <= result.raw_score <= 100, f"{title}: score {result.raw_score}"

            # Verify grade meets minimum expectation
            grade_order = {"A": 3, "B": 2, "C": 1}
            assert grade_order[result.grade] >= grade_order[grade_min], \
                f"{title}: grade {result.grade} < expected min {grade_min}"

    def test_regression_deterministic(self) -> None:
        """Same inputs always produce same output."""
        cfg = _default_config()
        ctx = _make_ctx(config=cfg, source_authority=0.8)
        entry = _make_entry(
            title="AI llm open source rust project",
            published=datetime(2026, 6, 30, 10, 0, 0, tzinfo=timezone.utc),
        )

        scores = [score(entry, ctx).raw_score for _ in range(10)]
        assert len(set(scores)) == 1, "Scoring should be deterministic"
