"""Repository — data access layer for SQLite storage."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from infodigest.collector.parser import Entry


def _row_to_entry(row: sqlite3.Row) -> Entry:
    """Convert a sqlite3.Row to an Entry dataclass."""
    published = None
    if row["published"]:
        try:
            published = datetime.fromisoformat(row["published"])
        except (ValueError, TypeError):
            published = None
    return Entry(
        uid=row["uid"],
        source_id=row["source_id"] or "",
        title=row["title"] or "",
        summary=row["summary"] or "",
        link=row["link"] or "",
        published=published,
        raw={},  # raw is not stored in DB
    )


class Repo:
    """Data access layer for InfoDigest SQLite storage."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_entries(self, entries: list[Entry]) -> int:
        """Insert or replace entries. Returns count of new inserts."""
        if not entries:
            return 0

        new_count = 0
        for e in entries:
            # Check if exists
            existing = self._conn.execute(
                "SELECT uid FROM entries WHERE uid = ?", (e.uid,)
            ).fetchone()

            pub_str = e.published.isoformat() if e.published else None
            self._conn.execute(
                """INSERT OR REPLACE INTO entries
                   (uid, source_id, title, summary, link, published, raw_score, grade, engagement)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (e.uid, e.source_id, e.title, e.summary, e.link,
                 pub_str, None, None, None),
            )
            if existing is None:
                new_count += 1

        self._conn.commit()
        return new_count

    def upsert_scored_entries(
        self,
        entries: list[tuple[Entry, float, str]],
    ) -> int:
        """Insert entries with scores. entries = [(Entry, score, grade), ...]"""
        if not entries:
            return 0

        new_count = 0
        for entry, raw_score, grade in entries:
            existing = self._conn.execute(
                "SELECT uid FROM entries WHERE uid = ?", (entry.uid,)
            ).fetchone()

            pub_str = entry.published.isoformat() if entry.published else None
            self._conn.execute(
                """INSERT OR REPLACE INTO entries
                   (uid, source_id, title, summary, link, published, raw_score, grade, engagement)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry.uid, entry.source_id, entry.title, entry.summary,
                 entry.link, pub_str, raw_score, grade, None),
            )
            if existing is None:
                new_count += 1

        self._conn.commit()
        return new_count

    def recent_titles(self, since_days: int = 7) -> list[str]:
        """Get normalized titles of entries from the last N days."""
        rows = self._conn.execute(
            """SELECT title FROM entries
               WHERE published >= datetime('now', ?)
               ORDER BY published DESC""",
            (f"-{since_days} days",),
        ).fetchall()
        return [row["title"] for row in rows]

    def pending_digest(self, grade_min: str = "B") -> list[Entry]:
        """Get entries that haven't been included in a digest yet, meeting grade threshold."""
        grade_order = {"A": 1, "B": 2, "C": 3}
        min_order = grade_order.get(grade_min, 2)

        # Build grade filter
        grades = [g for g, o in grade_order.items() if o <= min_order]
        if not grades:
            return []

        placeholders = ",".join("?" for _ in grades)
        rows = self._conn.execute(
            f"""SELECT * FROM entries
                WHERE digest_id IS NULL
                AND grade IN ({placeholders})
                ORDER BY raw_score DESC""",
            grades,
        ).fetchall()

        return [_row_to_entry(row) for row in rows]

    def mark_digest(
        self,
        entry_uids: list[str],
        digest_id: str,
    ) -> None:
        """Mark entries as belonging to a digest."""
        if not entry_uids:
            return
        placeholders = ",".join("?" for _ in entry_uids)
        self._conn.execute(
            f"UPDATE entries SET digest_id = ? WHERE uid IN ({placeholders})",
            [digest_id] + entry_uids,
        )
        self._conn.commit()

    def create_digest(
        self,
        digest_id: str,
        channel: str,
        entry_count: int,
        status: str = "sent",
        error: str | None = None,
    ) -> None:
        """Record a digest delivery."""
        self._conn.execute(
            """INSERT INTO digests (id, channel, entry_count, status, error)
               VALUES (?, ?, ?, ?, ?)""",
            (digest_id, channel, entry_count, status, error),
        )
        self._conn.commit()

    def start_run(self) -> int:
        """Start a new run record. Returns run ID."""
        cursor = self._conn.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(), "running"),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def finish_run(
        self,
        run_id: int,
        collected: int = 0,
        deduped: int = 0,
        rated: int = 0,
        delivered: int = 0,
        status: str = "success",
    ) -> None:
        """Update run record with final stats."""
        self._conn.execute(
            """UPDATE runs SET ended_at = ?, collected = ?, deduped = ?,
               rated = ?, delivered = ?, status = ?
               WHERE id = ?""",
            (datetime.now(timezone.utc).isoformat(), collected, deduped,
             rated, delivered, status, run_id),
        )
        self._conn.commit()

    def update_source_etag(
        self,
        source_id: str,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        """Update ETag/Last-Modified for incremental fetching."""
        self._conn.execute(
            "UPDATE sources SET etag = ?, last_modified = ? WHERE id = ?",
            (etag, last_modified, source_id),
        )
        self._conn.commit()

    def get_source_etag(self, source_id: str) -> tuple[str | None, str | None]:
        """Get cached ETag/Last-Modified for a source."""
        row = self._conn.execute(
            "SELECT etag, last_modified FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if row:
            return row["etag"], row["last_modified"]
        return None, None

    def upsert_source(
        self,
        source_id: str,
        url: str,
        category: str = "",
        authority: float = 0.5,
        lang: str = "",
        tags: str = "[]",
    ) -> None:
        """Insert or update a source record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO sources (id, url, category, authority, lang, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_id, url, category, authority, lang, tags),
        )
        self._conn.commit()

    def entry_count(self) -> int:
        """Total number of entries."""
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM entries").fetchone()
        return row["cnt"] if row else 0

    def entries_by_grade(self) -> dict[str, int]:
        """Count entries by grade."""
        rows = self._conn.execute(
            "SELECT grade, COUNT(*) as cnt FROM entries GROUP BY grade"
        ).fetchall()
        return {row["grade"]: row["cnt"] for row in rows if row["grade"]}
