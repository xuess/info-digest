"""Runner — orchestrates collect → rate → store → deliver pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from infodigest.config import Config
from infodigest.collector.fetcher import Fetcher
from infodigest.collector.parser import Source, Entry, parse
from infodigest.collector.dedup import dedup_entries
from infodigest.rater.scorer import RaterConfig, ScoreContext, ScoredEntry, score
from infodigest.storage.models import init_db
from infodigest.storage.repo import Repo
from infodigest.formatter.builder import build_feishu_card, build_dingtalk_md, chunk_entries
from infodigest.delivery.feishu import FeishuChannel
from infodigest.delivery.dingtalk import DingTalkChannel
from infodigest.delivery.limiter import feishu_limiter, dingtalk_limiter
from infodigest.delivery.failure import save_failed_digest

logger = logging.getLogger(__name__)


@dataclass
class RunReport:
    """Report of a pipeline run."""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    collected: int = 0
    deduped: int = 0
    rated: int = 0
    delivered: int = 0
    sources_ok: int = 0
    sources_failed: int = 0
    status: str = "running"
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None


def _load_sources(config_dir: Path) -> list[Source]:
    """Load sources from feeds.yaml."""
    path = config_dir / "feeds.yaml"
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    sources_data = raw.get("sources", [])
    return [Source.from_dict(d) for d in sources_data if d.get("enabled", True)]


def _load_rater_config(config_dir: Path) -> RaterConfig:
    """Load rater config from rater.yaml."""
    return RaterConfig.from_yaml(str(config_dir / "rater.yaml"))


def run(config: Config) -> RunReport:
    """Execute the full pipeline: collect → rate → store → deliver."""
    report = RunReport()
    config_dir = config.config_dir
    db_path = Path(config.storage.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Init storage
    conn = init_db(db_path)
    repo = Repo(conn)
    run_id = repo.start_run()

    # Load config
    sources = _load_sources(config_dir)
    rater_config = _load_rater_config(config_dir)

    # Register sources in DB
    for src in sources:
        repo.upsert_source(
            src.id, src.url, src.category, src.authority, src.lang,
            json.dumps(list(src.tags)),
        )

    # --- COLLECT ---
    all_entries: list[Entry] = []
    fetcher = Fetcher(
        timeout=config.collector.timeout,
        retries=config.collector.retries,
        user_agent=config.collector.user_agent,
    )

    try:
        for src in sources:
            try:
                etag, last_mod = repo.get_source_etag(src.id)
                result = fetcher.fetch(src.url, etag=etag, last_modified=last_mod)

                if result.not_modified:
                    logger.info("Source %s not modified, skipping", src.id)
                    report.sources_ok += 1
                    continue

                entries = parse(result.content, src)
                all_entries.extend(entries)

                # Update etag for incremental fetching
                repo.update_source_etag(src.id, result.etag, result.last_modified)
                report.sources_ok += 1

            except Exception as exc:
                logger.warning("Failed to collect %s: %s", src.id, exc)
                report.sources_failed += 1
                report.errors.append(f"collect:{src.id}:{exc}")
    finally:
        fetcher.close()

    report.collected = len(all_entries)
    logger.info("Collected %d entries from %d sources", report.collected, report.sources_ok)

    # --- DEDUP ---
    recent = repo.recent_titles(since_days=rater_config.dedup_window_days)
    deduped = dedup_entries(
        all_entries,
        recent_titles=recent,
        threshold=rater_config.dedup_similarity,
    )
    report.deduped = len(deduped)
    logger.info("After dedup: %d entries", report.deduped)

    # --- RATE ---
    ctx = ScoreContext(
        config=rater_config,
        source_authority=0.5,  # Will be overridden per entry
        recent_titles=recent,
    )

    scored: list[ScoredEntry] = []
    source_authority_map = {s.id: s.authority for s in sources}

    for entry in deduped:
        entry_ctx = ScoreContext(
            config=rater_config,
            source_authority=source_authority_map.get(entry.source_id, 0.5),
            recent_titles=recent,
        )
        scored.append(score(entry, entry_ctx))

    report.rated = len(scored)

    # --- STORE ---
    scored_tuples = [(e, e.raw_score, e.grade) for e in scored]
    repo.upsert_scored_entries(scored_tuples)

    # --- DELIVER ---
    pending = repo.pending_digest(rater_config.push_grade_min)
    if not pending:
        logger.info("No entries to deliver")
        report.status = "success"
        report.ended_at = datetime.now(timezone.utc)
        repo.finish_run(run_id, report.collected, report.deduped, report.rated, 0, "success")
        conn.close()
        return report

    # Re-score pending entries for delivery
    pending_scored: list[ScoredEntry] = []
    for entry in pending:
        entry_ctx = ScoreContext(
            config=rater_config,
            source_authority=source_authority_map.get(entry.source_id, 0.5),
            recent_titles=recent,
        )
        pending_scored.append(score(entry, entry_ctx))

    # Sort by score descending
    pending_scored.sort(key=lambda e: e.raw_score, reverse=True)

    # Chunk and deliver
    chunks = chunk_entries(pending_scored)

    for channel_name, channel_cfg in [
        ("feishu", config.delivery.feishu),
        ("dingtalk", config.delivery.dingtalk),
    ]:
        if not channel_cfg.enabled:
            continue

        webhook_url = channel_cfg.webhook_url
        if not webhook_url:
            logger.warning("No webhook URL for %s, skipping", channel_name)
            continue

        if channel_name == "feishu":
            channel = FeishuChannel(webhook_url)
            limiter = feishu_limiter()
        else:
            channel = DingTalkChannel(webhook_url, secret=channel_cfg.secret)
            limiter = dingtalk_limiter()

        for chunk in chunks:
            limiter.acquire()
            try:
                if channel_name == "feishu":
                    payload = json.dumps(build_feishu_card(chunk.entries, config_dir / "templates", translate=config.translate.enabled))
                else:
                    payload = build_dingtalk_md(chunk.entries, config_dir / "templates", translate=config.translate.enabled)

                success = channel.send(payload)
                if success:
                    report.delivered += len(chunk.entries)
                else:
                    save_failed_digest(channel_name, payload, "send returned False")
                    report.errors.append(f"deliver:{channel_name}:send_failed")
            except Exception as exc:
                logger.error("Delivery error for %s: %s", channel_name, exc)
                save_failed_digest(channel_name, str(exc), str(exc))
                report.errors.append(f"deliver:{channel_name}:{exc}")

    # Mark delivered entries
    delivered_uids = [e.uid for e in pending_scored[:report.delivered]]
    if delivered_uids:
        import uuid
        digest_id = uuid.uuid4().hex[:16]
        repo.mark_digest(delivered_uids, digest_id)
        repo.create_digest(digest_id, "multi", report.delivered, "sent")

    report.status = "success" if not report.errors else "partial"
    report.ended_at = datetime.now(timezone.utc)
    repo.finish_run(
        run_id, report.collected, report.deduped,
        report.rated, report.delivered, report.status,
    )
    conn.close()

    logger.info(
        "Run complete: collected=%d deduped=%d rated=%d delivered=%d status=%s",
        report.collected, report.deduped, report.rated, report.delivered, report.status,
    )
    return report
