"""Tests for storage/models.py and storage/repo.py"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from infodigest.storage.models import init_db
from infodigest.storage.repo import Repo
from infodigest.collector.parser import Entry


def _make_entry(
    uid: str = "uid1",
    title: str = "Test",
    source_id: str = "src",
    link: str = "https://example.com/a",
    published: datetime | None = None,
) -> Entry:
    return Entry(
        uid=uid,
        source_id=source_id,
        title=title,
        summary="summary",
        link=link,
        published=published or datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc),
        raw={},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    return Repo(conn)


class TestModels:
    def test_init_db_creates_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "entries" in tables
        assert "sources" in tables
        assert "digests" in tables
        assert "runs" in tables
        conn.close()

    def test_init_db_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn1 = init_db(db_path)
        conn1.close()
        conn2 = init_db(db_path)
        conn2.close()

    def test_init_db_creates_parent_dirs(self, tmp_path: Path) -> None:
        db_path = tmp_path / "deep" / "nested" / "test.db"
        conn = init_db(db_path)
        assert db_path.exists()
        conn.close()


class TestRepoUpsert:
    def test_upsert_new_entries(self, repo: Repo) -> None:
        entries = [_make_entry("uid1"), _make_entry("uid2")]
        count = repo.upsert_entries(entries)
        assert count == 2
        assert repo.entry_count() == 2

    def test_upsert_duplicate_entries(self, repo: Repo) -> None:
        entries = [_make_entry("uid1"), _make_entry("uid1")]
        count = repo.upsert_entries(entries)
        assert count == 1  # Second is duplicate
        assert repo.entry_count() == 1

    def test_upsert_empty(self, repo: Repo) -> None:
        assert repo.upsert_entries([]) == 0

    def test_upsert_scored_entries(self, repo: Repo) -> None:
        entries = [
            (_make_entry("uid1"), 85.0, "A"),
            (_make_entry("uid2"), 55.0, "B"),
        ]
        count = repo.upsert_scored_entries(entries)
        assert count == 2


class TestRepoQuery:
    def test_recent_titles(self, repo: Repo) -> None:
        entries = [_make_entry("uid1", title="Title 1")]
        repo.upsert_entries(entries)
        titles = repo.recent_titles(since_days=7)
        assert "Title 1" in titles

    def test_pending_digest(self, repo: Repo) -> None:
        entries = [
            (_make_entry("uid1"), 85.0, "A"),
            (_make_entry("uid2"), 55.0, "B"),
            (_make_entry("uid3"), 30.0, "C"),
        ]
        repo.upsert_scored_entries(entries)
        # Default push_grade_min = B → A and B
        pending = repo.pending_digest("B")
        assert len(pending) == 2

    def test_pending_digest_grade_c(self, repo: Repo) -> None:
        entries = [
            (_make_entry("uid1"), 85.0, "A"),
            (_make_entry("uid3"), 30.0, "C"),
        ]
        repo.upsert_scored_entries(entries)
        pending = repo.pending_digest("C")
        assert len(pending) == 2

    def test_pending_digest_empty(self, repo: Repo) -> None:
        assert repo.pending_digest("B") == []

    def test_entries_by_grade(self, repo: Repo) -> None:
        entries = [
            (_make_entry("uid1"), 85.0, "A"),
            (_make_entry("uid2"), 55.0, "B"),
            (_make_entry("uid3"), 30.0, "C"),
            (_make_entry("uid4"), 90.0, "A"),
        ]
        repo.upsert_scored_entries(entries)
        by_grade = repo.entries_by_grade()
        assert by_grade["A"] == 2
        assert by_grade["B"] == 1
        assert by_grade["C"] == 1


class TestRepoDigest:
    def test_mark_digest(self, repo: Repo) -> None:
        entries = [
            (_make_entry("uid1"), 50.0, "B"),
            (_make_entry("uid2"), 50.0, "B"),
        ]
        repo.upsert_scored_entries(entries)
        repo.mark_digest(["uid1"], "digest-1")
        pending = repo.pending_digest("C")
        pending_uids = [e.uid for e in pending]
        assert "uid1" not in pending_uids
        assert "uid2" in pending_uids

    def test_create_digest(self, repo: Repo) -> None:
        repo.create_digest("d1", "feishu", 5, "sent")
        row = repo._conn.execute("SELECT * FROM digests WHERE id = 'd1'").fetchone()
        assert row is not None
        assert row["channel"] == "feishu"
        assert row["entry_count"] == 5


class TestRepoRun:
    def test_start_and_finish_run(self, repo: Repo) -> None:
        run_id = repo.start_run()
        assert isinstance(run_id, int)
        repo.finish_run(run_id, collected=10, deduped=8, rated=8, delivered=5)
        row = repo._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row["collected"] == 10
        assert row["deduped"] == 8
        assert row["status"] == "success"


class TestRepoSource:
    def test_upsert_source(self, repo: Repo) -> None:
        repo.upsert_source("hn", "https://hnrss.org", "tech", 0.9)
        etag, lm = repo.get_source_etag("hn")
        assert etag is None
        assert lm is None

    def test_update_source_etag(self, repo: Repo) -> None:
        repo.upsert_source("hn", "https://hnrss.org")
        repo.update_source_etag("hn", '"v1"', "Mon, 30 Jun 2026 10:00:00 GMT")
        etag, lm = repo.get_source_etag("hn")
        assert etag == '"v1"'
        assert lm == "Mon, 30 Jun 2026 10:00:00 GMT"

    def test_get_source_etag_missing(self, repo: Repo) -> None:
        etag, lm = repo.get_source_etag("nonexistent")
        assert etag is None
        assert lm is None


class TestSourceHealth:
    def test_source_health_empty(self, repo: Repo) -> None:
        health = repo.source_health()
        assert health == []

    def test_source_health_with_data(self, repo: Repo) -> None:
        repo.upsert_source("src1", "https://a.com/feed", "tech", 0.8)
        repo.upsert_source("src2", "https://b.com/feed", "ai", 0.6)
        entries = [
            (_make_entry("uid1", source_id="src1"), 80.0, "A"),
            (_make_entry("uid2", source_id="src1"), 60.0, "B"),
            (_make_entry("uid3", source_id="src2"), 40.0, "C"),
        ]
        repo.upsert_scored_entries(entries)
        health = repo.source_health()
        assert len(health) == 2
        assert health[0]["id"] == "src1"
        assert health[0]["entry_count"] == 2
        assert health[1]["id"] == "src2"
        assert health[1]["entry_count"] == 1

    def test_disable_source(self, repo: Repo) -> None:
        repo.upsert_source("src1", "https://a.com/feed")
        repo.disable_source("src1")
        health = repo.source_health()
        assert health[0]["enabled"] is False

    def test_disable_nonexistent_source(self, repo: Repo) -> None:
        repo.disable_source("nonexistent")
