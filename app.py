"""Local web interface for managing freelance projects.

Usage:
    python app.py

Then open http://localhost:5001
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, redirect, render_template, request, url_for

from database.db import (
    get_applied_projects,
    get_ignored_projects,
    get_visible_projects,
    ignore_project,
    mark_project_applied,
    restore_project,
)
from models import Project
from ranking.scorer import score_project

app = Flask(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────


def _score_color(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "mid"
    return "low"


def _compute_keywords(description: str) -> tuple[list[str], list[str]]:
    """Re-compute matched/rejected keywords for display (score comes from DB)."""
    project = Project(
        id="", site="", title="", description=description,
        url="", budget=None, skills=[], published_at=None,
    )
    result = score_project(project)
    return result.matched_keywords, result.rejected_keywords


def _row_to_dict(row: dict[str, object]) -> dict[str, object]:
    """Convert a DB row to a template dict.  Uses stored score."""
    description = str(row["description"] or "")
    matched, rejected = _compute_keywords(description)
    score = int(row["score"] or 0)
    return {
        "project_id": row["project_id"],
        "site": row["site"],
        "title": row["title"],
        "url": row["url"],
        "description": description,
        "budget": row["budget"],
        "published_at": row["published_at"],
        "client": row["client"],
        "score": score,
        "color": _score_color(score),
        "matched": matched,
        "rejected": rejected,
    }


def _page_counts() -> dict[str, int]:
    """Count projects per page (each query hits only its own status)."""
    return {
        "active": len(get_visible_projects()),
        "applied": len(get_applied_projects()),
        "ignored": len(get_ignored_projects()),
    }


# ── Routes ──────────────────────────────────────────────────────────────


@app.get("/")
def index():
    rows = get_visible_projects()
    return render_template(
        "active.html",
        active_page="active",
        counts=_page_counts(),
        projects=[_row_to_dict(r) for r in rows],
    )


@app.post("/ignore/<site>/<project_id>")
def ignore(site: str, project_id: str):
    ignore_project(site, project_id)
    return redirect(url_for("index"))


@app.post("/apply/<site>/<project_id>")
def apply(site: str, project_id: str):
    mark_project_applied(site, project_id)
    return redirect(url_for("index"))


@app.get("/applied")
def applied():
    rows = get_applied_projects()
    return render_template(
        "applied.html",
        active_page="applied",
        counts=_page_counts(),
        projects=[_row_to_dict(r) for r in rows],
    )


@app.get("/ignored")
def ignored():
    rows = get_ignored_projects()
    return render_template(
        "ignored.html",
        active_page="ignored",
        counts=_page_counts(),
        projects=[_row_to_dict(r) for r in rows],
    )


@app.post("/restore/<site>/<project_id>")
def restore(site: str, project_id: str):
    restore_project(site, project_id)
    referrer = request.referrer or ""
    if "/applied" in referrer:
        return redirect(url_for("applied"))
    return redirect(url_for("ignored"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
