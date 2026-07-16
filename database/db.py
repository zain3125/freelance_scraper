"""SQLite database layer for project persistence."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models import Project
from ranking.rules import ACCEPT_THRESHOLD

_DB_PATH = Path(__file__).resolve().parent.parent / "freelance.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT    NOT NULL,
    site        TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    url         TEXT    UNIQUE,
    description TEXT,
    budget      TEXT,
    client      TEXT,
    published_at TEXT,
    score       INTEGER,
    status      TEXT    DEFAULT 'new',
    is_open     INTEGER NOT NULL DEFAULT 1,
    first_seen  TEXT    NOT NULL,
    last_seen   TEXT    NOT NULL,
    UNIQUE(site, project_id)
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    # Migrate existing databases that lack the is_open column.
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN is_open INTEGER NOT NULL DEFAULT 1")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists.


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ──────────────────────────────────────────────────────────


def save_project(project: Project, score: int) -> None:
    """Insert or update a project.  Sets is_open=1, preserves status."""
    conn = _connect()
    _ensure_schema(conn)
    now = _now()
    conn.execute(
        """
        INSERT INTO projects
            (project_id, site, title, url, description, budget,
             client, published_at, score, status, is_open, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', 1, ?, ?)
        ON CONFLICT(site, project_id) DO UPDATE SET
            title       = excluded.title,
            url         = excluded.url,
            description = excluded.description,
            budget      = excluded.budget,
            client      = excluded.client,
            published_at = excluded.published_at,
            score       = excluded.score,
            is_open     = 1,
            last_seen   = excluded.last_seen
        """,
        (
            project.id,
            project.site,
            project.title,
            project.url,
            project.description,
            project.budget,
            project.client,
            project.published_at,
            score,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()


def reset_open_status() -> None:
    """Set every project to is_open=0 before a new collection run."""
    conn = _connect()
    _ensure_schema(conn)
    conn.execute("UPDATE projects SET is_open = 0")
    conn.commit()
    conn.close()


def get_visible_projects() -> list[dict[str, object]]:
    """Return projects that are new, open, and score >= threshold."""
    conn = _connect()
    _ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT * FROM projects
        WHERE status = 'new' AND score >= ? AND is_open = 1
        ORDER BY score DESC
        """,
        (ACCEPT_THRESHOLD,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_applied_projects() -> list[dict[str, object]]:
    """Return applied projects that are still open."""
    conn = _connect()
    _ensure_schema(conn)
    rows = conn.execute(
        "SELECT * FROM projects WHERE status = 'applied' AND is_open = 1 ORDER BY last_seen DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ignored_projects() -> list[dict[str, object]]:
    """Return all ignored projects, newest first."""
    conn = _connect()
    _ensure_schema(conn)
    rows = conn.execute(
        "SELECT * FROM projects WHERE status = 'ignored' ORDER BY last_seen DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ignore_project(site: str, project_id: str) -> None:
    """Mark a project as ignored."""
    conn = _connect()
    _ensure_schema(conn)
    conn.execute(
        "UPDATE projects SET status = 'ignored' WHERE site = ? AND project_id = ?",
        (site, project_id),
    )
    conn.commit()
    conn.close()


def mark_project_applied(site: str, project_id: str) -> None:
    """Mark a project as applied."""
    conn = _connect()
    _ensure_schema(conn)
    conn.execute(
        "UPDATE projects SET status = 'applied' WHERE site = ? AND project_id = ?",
        (site, project_id),
    )
    conn.commit()
    conn.close()


def restore_project(site: str, project_id: str) -> None:
    """Restore an ignored or applied project back to 'new'."""
    conn = _connect()
    _ensure_schema(conn)
    conn.execute(
        "UPDATE projects SET status = 'new' WHERE site = ? AND project_id = ?",
        (site, project_id),
    )
    conn.commit()
    conn.close()


def get_pipeline_stats() -> dict[str, int]:
    """Return counts for pipeline logging."""
    conn = _connect()
    _ensure_schema(conn)
    rows = conn.execute(
        "SELECT status, is_open, COUNT(*) as cnt FROM projects GROUP BY status, is_open"
    ).fetchall()
    conn.close()
    stats: dict[str, int] = {}
    for r in rows:
        key = f"{r['status']}_{'open' if r['is_open'] else 'closed'}"
        stats[key] = r["cnt"]
    return stats
