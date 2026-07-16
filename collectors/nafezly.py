from __future__ import annotations
import logging
import re
import time

import httpx
from selectolax.parser import HTMLParser
from urllib.parse import urlencode

from config import NAFEZLY_PROJECTS_URL, NAFEZLY_SKILLS
from models import Project

log = logging.getLogger(__name__)

SITE_NAME = "nafezly"

# -- Selectors (centralize here for easy updates when Nafezly changes its HTML) --
SELECTOR_CARD = "div.project-box"
SELECTOR_TITLE_LINK = "a[href*='/project/']"
SELECTOR_DESCRIPTION = "h3.naskh"
SELECTOR_CLIENT_LINK = "a[href*='/u/']"
SELECTOR_ICON_BUDGET = "fa-usd-circle"
SELECTOR_ICON_PUBLISHED = "fa-clock"
SELECTOR_STATUS_ICON = "fa-check-circle"

_PROJECT_ID_RE = re.compile(r"/project/(\d+)")

def _build_projects_url(page: int = 1) -> str:
    """
    Build the Nafezly projects URL with the configured skills filter.
    """
    query = urlencode(
        {
            "skills": ",".join(NAFEZLY_SKILLS),
            "page": page,
        }
    )

    return f"{NAFEZLY_PROJECTS_URL}?{query}"

def collect() -> list[Project]:
    """Collect and return all open projects from Nafezly across all pages."""
    seen_ids: set[str] = set()
    all_projects: list[Project] = []
    page = 1

    while True:
        url = _build_projects_url(page)
        html = _download_page(url)
        tree = HTMLParser(html)
        cards = tree.css(SELECTOR_CARD)

        if not cards:
            break

        page_has_open = False

        for card in cards:
            if not _card_is_open(card):
                continue

            page_has_open = True

            try:
                project = _parse_single_project(card)
                if project is not None and project.id not in seen_ids:
                    seen_ids.add(project.id)
                    all_projects.append(project)
            except Exception:
                continue

        if not page_has_open:
            break

        page += 1

    return all_projects

def _download_page(url: str) -> str:
    """Download the projects page with retry and exponential backoff."""
    timeouts = httpx.Timeout(30, connect=10)
    for attempt in range(3):
        try:
            response = httpx.get(url, follow_redirects=True, timeout=timeouts)
            response.raise_for_status()
            return response.text
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            if attempt == 2:
                log.error("Nafezly request failed after 3 attempts: %s", exc)
                raise
            delay = 2 ** attempt
            log.warning("Nafezly request failed (attempt %d), retrying in %ds: %s", attempt + 1, delay, exc)
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
    budget = _text_near_icon(card, SELECTOR_ICON_BUDGET)
    published_at = _text_near_icon(card, SELECTOR_ICON_PUBLISHED)
    client = _extract_client(card)

    return Project(
        id=project_id,
        site=SITE_NAME,
        title=title,
        description=description or "",
        url=_build_project_url(project_id),
        budget=budget,
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
    for link in card.css(SELECTOR_CLIENT_LINK):
        name = link.text(strip=True)
        if name:
            return name
    return None

def _build_project_url(project_id: str) -> str:
    """Build canonical Nafezly project URL from the project ID."""
    return f"https://nafezly.com/project/{project_id}"


def _extract_project_id(url: str) -> str | None:
    """Extract the numeric project ID from a Nafezly project URL."""
    match = _PROJECT_ID_RE.search(url)
    return match.group(1) if match else None

def _text_near_icon(card, icon_class: str) -> str | None:
    """Extract text from the parent span that wraps a Font Awesome icon."""
    icon = card.css_first(f"span.{icon_class}")
    if icon is None:
        return None
    parent = icon.parent
    if parent is None:
        return None
    return parent.text(strip=True) or None

def _card_is_open(card) -> bool:
    """Check if a project card has status 'مفتوح' (open)."""
    icon = card.css_first(f"span.{SELECTOR_STATUS_ICON}")
    if icon is None:
        return False
    parent = icon.parent
    if parent is None:
        return False
    return "مفتوح" in parent.text(strip=True)
