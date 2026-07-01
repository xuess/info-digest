"""SQLite table definitions and initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    category TEXT,
    lang TEXT,
    authority REAL DEFAULT 0.5,
    tags TEXT,
    etag TEXT,
    last_modified TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entries (
    uid TEXT PRIMARY KEY,
    source_id TEXT,
    title TEXT,
    summary TEXT,
    link TEXT,
    published TEXT,
    raw_score REAL,
    grade TEXT,
    engagement INTEGER,
    digest_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entries_published ON entries(published);
CREATE INDEX IF NOT EXISTS idx_entries_grade ON entries(grade);
CREATE INDEX IF NOT EXISTS idx_entries_source_id ON entries(source_id);

CREATE TABLE IF NOT EXISTS digests (
    id TEXT PRIMARY KEY,
    created_at TEXT DEFAULT (datetime('now')),
    channel TEXT,
    entry_count INTEGER,
    status TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    ended_at TEXT,
    collected INTEGER DEFAULT 0,
    deduped INTEGER DEFAULT 0,
    rated INTEGER DEFAULT 0,
    delivered INTEGER DEFAULT 0,
    status TEXT
);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Initialize database with schema. Creates parent dirs if needed."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Get a connection to an existing database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
