"""Collector manager – runs all collectors and merges results."""

from __future__ import annotations

import logging

from collectors import nafezly, mostaql
from models import Project

log = logging.getLogger(__name__)

_COLLECTORS = [
    ("nafezly", nafezly.collect),
    ("mostaql", mostaql.collect),
]


def collect_all() -> list[Project]:
    """Run every registered collector and return the combined projects.

    If a single collector fails the error is logged and the remaining
    collectors still run.
    """
    all_projects: list[Project] = []

    for name, fn in _COLLECTORS:
        try:
            projects = fn()
            log.info("%s returned %d projects", name, len(projects))
            all_projects.extend(projects)
        except Exception:
            log.exception("Collector %s failed", name)

    return all_projects
