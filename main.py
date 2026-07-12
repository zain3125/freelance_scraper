"""Freelance job finder – daily pipeline.

Usage:
    python main.py

Collects projects from Nafezly and Mostaql, scores them, persists
everything to SQLite, and writes report.html with active projects only.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors.manager import collect_all
from database.db import get_active_projects, save_project
from models import Project
from ranking.scorer import score_project
from reporting.html_report import generate_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def _row_to_project(row: dict[str, object]) -> Project:
    """Convert a database row back into a Project."""
    return Project(
        id=str(row["project_id"]),
        site=str(row["site"]),
        title=str(row["title"]),
        description=str(row["description"] or ""),
        url=str(row["url"] or ""),
        budget=str(row["budget"]) if row["budget"] else None,
        skills=[],
        published_at=str(row["published_at"]) if row["published_at"] else None,
        client=str(row["client"]) if row["client"] else None,
    )


def _main() -> None:
    log.info("Starting freelance job finder")

    # 1. Collect from all sources
    projects = collect_all()
    log.info("Collected %d projects total", len(projects))

    # 2. Score and save
    for project in projects:
        result = score_project(project)
        save_project(project, result.score)
    log.info("Saved %d projects to database", len(projects))

    # 3. Load active projects and re-score for keyword display
    active_rows = get_active_projects()
    log.info("Active projects: %d", len(active_rows))

    scored: list[tuple[Project, object]] = []

    for row in active_rows:
        project = _row_to_project(row)
        result = score_project(project)

        if result.accepted:
            scored.append((project, result))

    # 4. Generate report
    report_path = generate_report(scored, total_collected=len(projects))
    log.info("Report written to %s", report_path)


if __name__ == "__main__":
    _main()
