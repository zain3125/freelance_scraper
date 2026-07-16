"""Freelance job finder – daily pipeline.

Usage:
    python main.py

Collects projects from Nafezly and Mostaql, scores them, persists
everything to SQLite, and writes report.html with visible projects only.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors.manager import collect_all
from database.db import (
    get_applied_projects,
    get_ignored_projects,
    get_pipeline_stats,
    get_visible_projects,
    reset_open_status,
    save_project,
)
from models import Project
from ranking.rules import ACCEPT_THRESHOLD
from ranking.scorer import ProjectScore, score_project
from reporting.html_report import generate_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def _row_to_report(row: dict[str, object]) -> tuple[Project, ProjectScore]:
    """Build a (Project, ProjectScore) pair from a DB row using stored score."""
    project = Project(
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
    result = score_project(project)
    stored_score = int(row["score"] or 0)
    score_result = ProjectScore(
        score=stored_score,
        accepted=stored_score >= ACCEPT_THRESHOLD,
        matched_keywords=result.matched_keywords,
        rejected_keywords=result.rejected_keywords,
        reasons=result.reasons,
    )
    return project, score_result


def _main() -> None:
    log.info("Starting freelance job finder")

    # 1. Reset open status before collecting
    reset_open_status()

    # 2. Collect from all sources
    projects = collect_all()
    log.info("Collected today: %d", len(projects))

    # 3. Score and save (sets is_open=1 for each saved project)
    for project in projects:
        result = score_project(project)
        save_project(project, result.score)

    # 4. Load visible projects
    visible_rows = get_visible_projects()

    # 5. Build report data using stored scores
    scored = [_row_to_report(row) for row in visible_rows]

    # 6. Generate report
    report_path = generate_report(scored, total_collected=len(projects))
    log.info("Report written to %s", report_path)

    # 7. Log pipeline stats
    stats = get_pipeline_stats()
    open_new = stats.get("new_open", 0)
    closed = stats.get("new_closed", 0)
    ignored = stats.get("ignored_open", 0) + stats.get("ignored_closed", 0)
    applied = stats.get("applied_open", 0) + stats.get("applied_closed", 0)
    log.info("Open projects: %d", open_new)
    log.info("Closed since yesterday: %d", closed)
    log.info("Ignored: %d", ignored)
    log.info("Applied: %d", applied)
    log.info("Visible today: %d", len(visible_rows))


if __name__ == "__main__":
    _main()
