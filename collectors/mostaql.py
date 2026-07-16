from __future__ import annotations

import logging
import re
import time

import httpx
from selectolax.parser import HTMLParser
from urllib.parse import urlencode

from config import MOSTAQL_PROJECTS_URL, MOSTAQL_SKILLS
from models import Project

log = logging.getLogger(__name__)

SITE_NAME = "mostaql"

# -- Selectors (centralize here for easy updates when Mostaql changes its HTML) --
SELECTOR_CARD = "tr.project-row"
SELECTOR_TITLE_LINK = "h2.mrg--bt-reset > a"
SELECTOR_DESCRIPTION = "p.project__brief a.details-url"
SELECTOR_CLIENT = "ul.project__meta li.text-muted bdi"
SELECTOR_DATE = 'time[itemprop="datePublished"]'

_PROJECT_ID_RE = re.compile(r"/project/(\d+)")


def _build_projects_url(page: int = 1) -> str:
    """Build the Mostaql projects URL with the configured skills filter."""
    query = urlencode({"page": page, "skills": ",".join(MOSTAQL_SKILLS)})
    return f"{MOSTAQL_PROJECTS_URL}?{query}"


def collect() -> list[Project]:
    """Collect and return all projects from Mostaql across all pages."""
    seen_ids: set[str] = set()
    all_projects: list[Project] = []
    page = 1

    while True:
        url = _build_projects_url(page)
        html = _download_page(url)

        page_projects = _parse_project_cards(html)

        if not page_projects:
            break

        for project in page_projects:
            if project.id not in seen_ids:
                seen_ids.add(project.id)
                all_projects.append(project)

        page += 1

    return all_projects


def _download_page(url: str) -> str:
    """Download the projects page with retry and exponential backoff."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
    }
    timeouts = httpx.Timeout(30, connect=10)
    for attempt in range(3):
        try:
            client = httpx.Client(follow_redirects=True, timeout=timeouts, headers=headers)
            with client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            if attempt == 2:
                log.error("Mostaql request failed after 3 attempts: %s", exc)
                raise
            delay = 2 ** attempt
            log.warning("Mostaql request failed (attempt %d), retrying in %ds: %s", attempt + 1, delay, exc)
            time.sleep(delay)


def _parse_project_cards(html: str) -> list[Project]:
    """Parse all project cards from HTML into Project objects."""
    tree = HTMLParser(html)
    cards = tree.css(SELECTOR_CARD)
    projects: list[Project] = []

    for card in cards:
        try:
            project = _parse_single_project(card)
            if project is not None:
                projects.append(project)
        except Exception:
            continue

    return projects


def _parse_single_project(card) -> Project | None:
    """Parse a single project card element into a Project."""
    title, url = _extract_title_and_url(card)
    if not title or not url:
        return None

    project_id = _extract_project_id(url)
    if not project_id:
        return None

    description = _extract_description(card)
    published_at = _extract_published_at(card)
    client = _extract_client(card)

    return Project(
        id=project_id,
        site=SITE_NAME,
        title=title,
        description=description or "",
        url=_build_project_url(project_id),
        budget=None,
        skills=[],
        published_at=published_at,
        client=client,
    )


def _extract_title_and_url(card) -> tuple[str | None, str | None]:
    """Extract the project title text and URL from a card."""
    link = card.css_first(SELECTOR_TITLE_LINK)
    if link is None:
        return None, None
    url = link.attributes.get("href")
    title = link.text(strip=True)
    return title or None, url or None


def _extract_description(card) -> str | None:
    """Extract the project description snippet from a card."""
    el = card.css_first(SELECTOR_DESCRIPTION)
    return el.text(strip=True) if el else None


def _extract_client(card) -> str | None:
    """Extract the client name from a card."""
    el = card.css_first(SELECTOR_CLIENT)
    return el.text(strip=True) if el else None


def _extract_published_at(card) -> str | None:
    """Extract the absolute publication timestamp from a card."""
    el = card.css_first(SELECTOR_DATE)
    if el is None:
        return None
    return el.attributes.get("datetime") or None


def _build_project_url(project_id: str) -> str:
    """Build canonical Mostaql project URL from the project ID."""
    return f"https://mostaql.com/project/{project_id}"


def _extract_project_id(url: str) -> str | None:
    """Extract the numeric project ID from a Mostaql project URL."""
    match = _PROJECT_ID_RE.search(url)
    return match.group(1) if match else None
