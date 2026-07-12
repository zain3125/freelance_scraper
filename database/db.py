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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ──────────────────────────────────────────────────────────


def save_project(project: Project, score: int) -> None:
    """Insert or update a project.  Never resets an existing 'ignored' status."""
    conn = _connect()
    _ensure_schema(conn)
    now = _now()
    conn.execute(
        """
        INSERT INTO projects
            (project_id, site, title, url, description, budget,
             client, published_at, score, status, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
        ON CONFLICT(site, project_id) DO UPDATE SET
            title       = excluded.title,
            url         = excluded.url,
            description = excluded.description,
            budget      = excluded.budget,
            client      = excluded.client,
            published_at = excluded.published_at,
            score       = excluded.score,
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


def get_active_projects() -> list[dict[str, object]]:
    """Return all projects where status != 'ignored', newest first."""
    conn = _connect()
    _ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT *
        FROM projects
        WHERE status != 'ignored'
        AND score >= ?
        ORDER BY score DESC, last_seen DESC
        """,
        (ACCEPT_THRESHOLD,)
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
