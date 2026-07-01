"""CLI entry point — argparse subcommands."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from infodigest.config import load_config
from infodigest.scheduler.runner import run as run_pipeline


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> None:
    """Execute full pipeline: collect → rate → store → deliver."""
    config = load_config(args.config)
    report = run_pipeline(config)
    print(f"\n{'='*50}")
    print(f"Run Report")
    print(f"{'='*50}")
    print(f"  Collected:  {report.collected}")
    print(f"  After dedup: {report.deduped}")
    print(f"  Rated:      {report.rated}")
    print(f"  Delivered:  {report.delivered}")
    print(f"  Sources OK: {report.sources_ok}  Failed: {report.sources_failed}")
    print(f"  Status:     {report.status}")
    if report.errors:
        print(f"  Errors:")
        for err in report.errors:
            print(f"    - {err}")
    if report.duration_seconds:
        print(f"  Duration:   {report.duration_seconds:.1f}s")
    print(f"{'='*50}")

    if report.status not in ("success", "partial"):
        sys.exit(1)


def cmd_collect(args: argparse.Namespace) -> None:
    """Only collect and store (no delivery)."""
    from infodigest.collector.fetcher import Fetcher
    from infodigest.collector.parser import Source, parse
    from infodigest.collector.dedup import dedup_entries
    from infodigest.storage.models import init_db
    from infodigest.storage.repo import Repo
    from infodigest.rater.scorer import RaterConfig
    import yaml

    config = load_config(args.config)
    rater_config = RaterConfig.from_yaml(str(config.config_dir / "rater.yaml"))

    conn = init_db(config.storage.db_path)
    repo = Repo(conn)

    with open(config.config_dir / "feeds.yaml") as f:
        raw = yaml.safe_load(f) or {}
    sources = [Source.from_dict(d) for d in raw.get("sources", []) if d.get("enabled", True)]

    fetcher = Fetcher(timeout=config.collector.timeout, retries=config.collector.retries)
    total = 0
    try:
        for src in sources:
            try:
                etag, last_mod = repo.get_source_etag(src.id)
                result = fetcher.fetch(src.url, etag=etag, last_modified=last_mod)
                if result.not_modified:
                    print(f"  {src.id}: not modified")
                    continue
                entries = parse(result.content, src)
                recent = repo.recent_titles(rater_config.dedup_window_days)
                deduped = dedup_entries(entries, recent, rater_config.dedup_similarity)
                new_count = repo.upsert_entries(deduped)
                repo.update_source_etag(src.id, result.etag, result.last_modified)
                total += new_count
                print(f"  {src.id}: +{new_count} new entries")
            except Exception as exc:
                print(f"  {src.id}: FAILED — {exc}")
    finally:
        fetcher.close()

    print(f"\nTotal new entries: {total}")
    conn.close()


def cmd_report(args: argparse.Namespace) -> None:
    """Show recent run stats."""
    from infodigest.storage.models import get_connection

    config = load_config(args.config)
    conn = get_connection(config.storage.db_path)
    conn.row_factory = __import__("sqlite3").Row

    rows = conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT 10"
    ).fetchall()

    if not rows:
        print("No runs found.")
        return

    print(f"{'ID':>4} {'Started':<20} {'Collected':>10} {'Deduped':>8} {'Rated':>6} {'Delivered':>10} {'Status':<10}")
    print("-" * 75)
    for row in rows:
        print(
            f"{row['id']:>4} {str(row['started_at'] or ''):<20} "
            f"{row['collected'] or 0:>10} {row['deduped'] or 0:>8} "
            f"{row['rated'] or 0:>6} {row['delivered'] or 0:>10} "
            f"{row['status'] or '':<10}"
        )
    conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="info-digest",
        description="RSS-based information aggregator",
    )
    parser.add_argument(
        "-c", "--config",
        default="config",
        help="Config directory (default: config)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Full pipeline: collect → rate → store → deliver")
    subparsers.add_parser("collect", help="Collect and store only (no delivery)")
    subparsers.add_parser("report", help="Show recent run statistics")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "run": cmd_run,
        "collect": cmd_collect,
        "report": cmd_report,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
