"""Rule-based scorer — five dimensions, no LLM."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import yaml

from infodigest.collector.parser import Entry
from infodigest.collector.normalizer import normalize_title, strip_html


@dataclass(frozen=True)
class RaterConfig:
    """Rating configuration loaded from rater.yaml."""
    weights: dict[str, int]
    freshness_half_life_hours: float
    max_age_hours: float
    relevance_target: float
    engagement_threshold: float
    grade_thresholds: dict[str, int]
    push_grade_min: str
    keywords: dict[str, float]
    dedup_similarity: float
    dedup_window_days: int

    @classmethod
    def from_yaml(cls, path: str = "config/rater.yaml") -> RaterConfig:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        return cls(
            weights=raw.get("weights", {
                "authority": 30, "freshness": 25, "relevance": 25,
                "uniqueness": 10, "engagement": 10,
            }),
            freshness_half_life_hours=raw.get("freshness_half_life_hours", 72),
            max_age_hours=raw.get("max_age_hours", 168),
            relevance_target=raw.get("relevance_target", 3.0),
            engagement_threshold=raw.get("engagement_threshold", 200),
            grade_thresholds=raw.get("grade_thresholds", {"A": 75, "B": 50}),
            push_grade_min=raw.get("push_grade_min", "B"),
            keywords=raw.get("keywords", {}),
            dedup_similarity=raw.get("dedup_similarity", 0.8),
            dedup_window_days=raw.get("dedup_window_days", 7),
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RaterConfig:
        return cls(
            weights=d.get("weights", {
                "authority": 30, "freshness": 25, "relevance": 25,
                "uniqueness": 10, "engagement": 10,
            }),
            freshness_half_life_hours=d.get("freshness_half_life_hours", 72),
            max_age_hours=d.get("max_age_hours", 168),
            relevance_target=d.get("relevance_target", 3.0),
            engagement_threshold=d.get("engagement_threshold", 200),
            grade_thresholds=d.get("grade_thresholds", {"A": 75, "B": 50}),
            push_grade_min=d.get("push_grade_min", "B"),
            keywords=d.get("keywords", {}),
            dedup_similarity=d.get("dedup_similarity", 0.8),
            dedup_window_days=d.get("dedup_window_days", 7),
        )


@dataclass(frozen=True)
class ScoreContext:
    """Context needed for scoring: config + external data."""
    config: RaterConfig
    source_authority: float  # From feeds.yaml
    recent_titles: list[str]  # For uniqueness


@dataclass(frozen=True)
class ScoredEntry:
    """Entry with score and grade."""
    uid: str
    source_id: str
    title: str
    summary: str
    link: str
    published: datetime | None
    raw: dict[str, Any]
    raw_score: float
    grade: str


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _freshness_score(
    published: datetime | None,
    half_life: float,
    max_age: float,
    now: datetime | None = None,
) -> float:
    """Compute freshness score: exp(-Δh/half_life), 0 if older than max_age."""
    if published is None:
        return 1.0  # No time → treat as fresh
    if now is None:
        now = datetime.now(timezone.utc)
    delta_hours = (now - published).total_seconds() / 3600
    if delta_hours < 0:
        delta_hours = 0  # Future dates treated as now
    if delta_hours > max_age:
        return 0.0
    return math.exp(-delta_hours / half_life)


def _relevance_score(
    title: str,
    summary: str,
    keywords: dict[str, float],
    target: float,
) -> float:
    """Compute keyword relevance: title hits ×1.0, summary hits ×0.4."""
    if not keywords:
        return 0.5  # Neutral when no keywords configured

    title_lower = title.lower()
    summary_text = strip_html(summary).lower() if summary else ""

    total = 0.0
    for word, weight in keywords.items():
        w = word.lower()
        if w in title_lower:
            total += weight * 1.0
        if w in summary_text:
            total += weight * 0.4

    return min(total / target, 1.0) if target > 0 else 0.0


def _uniqueness_score(
    title: str,
    recent_titles: list[str],
) -> float:
    """Compute uniqueness: 1 - max_jaccard_similar(title, recent)."""
    if not recent_titles:
        return 1.0

    words = set(_WORD_RE.findall(normalize_title(title).lower()))
    if not words:
        return 1.0

    max_sim = 0.0
    for recent in recent_titles:
        recent_words = set(_WORD_RE.findall(recent.lower()))
        if not recent_words:
            continue
        intersection = words & recent_words
        union = words | recent_words
        sim = len(intersection) / len(union) if union else 0.0
        max_sim = max(max_sim, sim)

    return 1.0 - max_sim


def _engagement_score(raw: dict[str, Any], threshold: float) -> float:
    """Compute engagement from raw entry data (comments/points)."""
    for key in ("points", "score", "comments_count", "comments"):
        val = raw.get(key)
        if val is not None:
            try:
                num = float(val)
                return min(num / threshold, 1.0) if threshold > 0 else 0.0
            except (ValueError, TypeError):
                continue
    return 0.0


def _grade(score: float, thresholds: dict[str, int]) -> str:
    """Assign grade: A if >= A_threshold, B if >= B_threshold, else C."""
    a_threshold = thresholds.get("A", 75)
    b_threshold = thresholds.get("B", 50)
    if score >= a_threshold:
        return "A"
    if score >= b_threshold:
        return "B"
    return "C"


def score(entry: Entry, ctx: ScoreContext) -> ScoredEntry:
    """Score an entry using five dimensions. Pure function, no IO."""
    cfg = ctx.config
    w = cfg.weights

    authority = min(max(ctx.source_authority, 0.0), 1.0)
    freshness = _freshness_score(
        entry.published,
        cfg.freshness_half_life_hours,
        cfg.max_age_hours,
    )
    relevance = _relevance_score(
        entry.title,
        entry.summary,
        cfg.keywords,
        cfg.relevance_target,
    )
    uniqueness = _uniqueness_score(entry.title, ctx.recent_titles)
    engagement = _engagement_score(entry.raw, cfg.engagement_threshold)

    raw_score = (
        w.get("authority", 30) * authority
        + w.get("freshness", 25) * freshness
        + w.get("relevance", 25) * relevance
        + w.get("uniqueness", 10) * uniqueness
        + w.get("engagement", 10) * engagement
    )
    raw_score = max(0.0, min(100.0, raw_score))
    grade = _grade(raw_score, cfg.grade_thresholds)

    return ScoredEntry(
        uid=entry.uid,
        source_id=entry.source_id,
        title=entry.title,
        summary=entry.summary,
        link=entry.link,
        published=entry.published,
        raw=entry.raw,
        raw_score=round(raw_score, 2),
        grade=grade,
    )
