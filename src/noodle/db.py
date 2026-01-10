"""
Database module for Noodle.

SQLite storage with FTS5 full-text search.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from noodle.config import get_db_path, get_noodle_home

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Core entries table
-- TYPE CONSTRAINT: Only 4 types, FROZEN forever. Extend via tags, not new types.
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,                    -- Unix timestamp ms
    created_at TEXT NOT NULL,               -- ISO 8601
    updated_at TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('task', 'thought', 'person', 'event')),
    title TEXT NOT NULL,
    body TEXT,
    confidence REAL NOT NULL,
    priority TEXT CHECK(priority IN ('low', 'medium', 'high')),
    due_date TEXT,                          -- ISO 8601 date
    completed_at TEXT,                      -- For tasks
    project_id TEXT REFERENCES projects(id),
    source TEXT DEFAULT 'cli',              -- cli, telegram, api, etc.
    raw_input TEXT NOT NULL,                -- Original unprocessed text
    markdown_path TEXT,                     -- Path to .md file if exists
    needs_reclassification INTEGER DEFAULT 0
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,                    -- slug
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'paused', 'completed', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- People/Contacts
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,                    -- slug
    name TEXT NOT NULL,
    email TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Tags (many-to-many)
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id TEXT REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

-- Entry-People relationships
CREATE TABLE IF NOT EXISTS entry_people (
    entry_id TEXT REFERENCES entries(id) ON DELETE CASCADE,
    person_id TEXT REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, person_id)
);

-- Classifier audit log
CREATE TABLE IF NOT EXISTS classifier_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT REFERENCES entries(id),
    timestamp TEXT NOT NULL,
    raw_input TEXT NOT NULL,
    llm_output TEXT NOT NULL,               -- Full JSON response
    llm_model TEXT NOT NULL,
    confidence REAL NOT NULL,
    processing_time_ms INTEGER,
    status TEXT NOT NULL,                   -- classified, fallback, manual_review, error
    routed_to TEXT
);

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title,
    body,
    content='entries',
    content_rowid='rowid'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type);
CREATE INDEX IF NOT EXISTS idx_entries_project ON entries(project_id);
CREATE INDEX IF NOT EXISTS idx_entries_due_date ON entries(due_date);
CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
CREATE INDEX IF NOT EXISTS idx_entries_needs_reclass ON entries(needs_reclassification);

-- FTS triggers
CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
    INSERT INTO entries_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
END;
"""


class Database:
    """SQLite database wrapper for Noodle."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_db_path()
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database exists and schema is current."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            # Set schema version
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def insert_entry(self, entry: dict[str, Any]) -> str:
        """Insert a classified entry. Returns entry ID."""
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO entries (
                    id, created_at, updated_at, type, title, body,
                    confidence, priority, due_date, project_id,
                    source, raw_input, needs_reclassification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["id"],
                entry.get("created_at", now),
                now,
                entry["type"],
                entry["title"],
                entry.get("body"),
                entry["confidence"],
                entry.get("priority"),
                entry.get("due_date"),
                entry.get("project"),
                entry.get("source", "cli"),
                entry["raw_input"],
                entry.get("needs_reclassification", 0),
            ))

            # Handle tags
            if tags := entry.get("tags"):
                for tag_name in tags:
                    # Insert or get tag
                    conn.execute(
                        "INSERT OR IGNORE INTO tags (name) VALUES (?)",
                        (tag_name.lower(),)
                    )
                    tag_id = conn.execute(
                        "SELECT id FROM tags WHERE name = ?",
                        (tag_name.lower(),)
                    ).fetchone()[0]
                    conn.execute(
                        "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                        (entry["id"], tag_id)
                    )

            # Handle people references
            if people := entry.get("people"):
                for person_slug in people:
                    # Ensure person exists (create stub if not)
                    conn.execute("""
                        INSERT OR IGNORE INTO people (id, name, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (person_slug, person_slug.replace("-", " ").title(), now, now))
                    conn.execute(
                        "INSERT OR IGNORE INTO entry_people (entry_id, person_id) VALUES (?, ?)",
                        (entry["id"], person_slug)
                    )

        return entry["id"]

    def log_classification(
        self,
        entry_id: str,
        raw_input: str,
        llm_output: str,
        llm_model: str,
        confidence: float,
        processing_time_ms: int,
        status: str,
        routed_to: str | None = None,
    ) -> None:
        """Log a classification attempt for auditing."""
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO classifier_logs (
                    entry_id, timestamp, raw_input, llm_output,
                    llm_model, confidence, processing_time_ms, status, routed_to
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_id, now, raw_input, llm_output,
                llm_model, confidence, processing_time_ms, status, routed_to
            ))

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Get a single entry by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM entries WHERE id = ?", (entry_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None

    def get_entries(
        self,
        entry_type: str | None = None,
        project: str | None = None,
        limit: int = 20,
        include_completed: bool = False,
    ) -> list[dict[str, Any]]:
        """Get entries with optional filters."""
        query = "SELECT * FROM entries WHERE 1=1"
        params: list[Any] = []

        if entry_type:
            query += " AND type = ?"
            params.append(entry_type)

        if project:
            query += " AND project_id = ?"
            params.append(project)

        if not include_completed:
            query += " AND (completed_at IS NULL OR type != 'task')"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Full-text search across entries."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT e.* FROM entries e
                JOIN entries_fts fts ON e.rowid = fts.rowid
                WHERE entries_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit)).fetchall()
            return [dict(row) for row in rows]

    def complete_task(self, entry_id: str) -> bool:
        """Mark a task as complete. Returns True if successful."""
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE entries
                SET completed_at = ?, updated_at = ?
                WHERE id = ? AND type = 'task' AND completed_at IS NULL
            """, (now, now, entry_id))
            return cursor.rowcount > 0

    def update_entry_type(self, entry_id: str, new_type: str) -> bool:
        """Change an entry's type. Returns True if successful."""
        if new_type not in ('task', 'thought', 'person', 'event'):
            raise ValueError(f"Invalid type: {new_type}")

        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE entries
                SET type = ?, updated_at = ?, needs_reclassification = 0
                WHERE id = ?
            """, (new_type, now, entry_id))
            return cursor.rowcount > 0

    def get_pending_reclassification(self) -> list[dict[str, Any]]:
        """Get entries that need manual reclassification."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM entries
                WHERE needs_reclassification = 1
                ORDER BY created_at DESC
            """).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            by_type = dict(conn.execute("""
                SELECT type, COUNT(*) FROM entries GROUP BY type
            """).fetchall())
            pending = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE needs_reclassification = 1"
            ).fetchone()[0]

            return {
                "total_entries": total,
                "by_type": by_type,
                "pending_reclassification": pending,
            }
