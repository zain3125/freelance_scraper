"""Deterministic rule-based scoring engine for freelance projects."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from models import Project
from ranking.rules import (
    ACCEPT_THRESHOLD,
    NEGATIVE_AR,
    NEGATIVE_EN,
    NEGATIVE_POINTS,
    POSITIVE_AR,
    POSITIVE_EN,
    POSITIVE_POINTS,
)

# Matches any non-alphanumeric, non-whitespace character (including Arabic
# diacritics / tashkeel).  We strip these before matching so that minor
# punctuation differences never prevent a keyword from being found.
_PUNCT_RE = re.compile(r"[^\w\s\u0600-\u06FF]")


@dataclass(frozen=True)
class ProjectScore:
    """Result of scoring a single project."""

    score: int
    accepted: bool
    matched_keywords: list[str] = field(default_factory=list)
    rejected_keywords: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


# ── Public API ──────────────────────────────────────────────────────────


def score_project(project: Project) -> ProjectScore:
    """Return a deterministic score for *project*.

    The score is computed purely from the project's title and description.
    No randomness, no AI, no network calls.
    """
    text = _normalize(project.title + " " + project.description)

    matched_pos, pos_reasons = _match_keywords(text, POSITIVE_EN + POSITIVE_AR)
    matched_neg, neg_reasons = _match_keywords(text, NEGATIVE_EN + NEGATIVE_AR)

    raw = 40  # neutral starting point
    raw += len(matched_pos) * POSITIVE_POINTS
    raw -= len(matched_neg) * NEGATIVE_POINTS

    score = max(0, min(100, raw))

    reasons: list[str] = []
    if pos_reasons:
        reasons.append("Positive signals: " + ", ".join(pos_reasons))
    if neg_reasons:
        reasons.append("Negative signals: " + ", ".join(neg_reasons))
    if not reasons:
        reasons.append("No strong keyword signals found")

    return ProjectScore(
        score=score,
        accepted=score >= ACCEPT_THRESHOLD,
        matched_keywords=matched_pos,
        rejected_keywords=matched_neg,
        reasons=reasons,
    )


# ── Internal helpers ────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace, remove punctuation."""
    text = text.lower()
    # Strip Arabic diacritics (tashkeel / harakat) so they never block a match.
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = unicodedata.normalize("NFC", text)
    # Remove punctuation, then collapse whitespace.
    text = _PUNCT_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _match_keywords(
    text: str, keywords: list[str]
) -> tuple[list[str], list[str]]:
    """Return (unique_matched_keywords, human_readable_reasons).

    Matching is case-insensitive substring containment.  Longer keywords
    are checked first so that, for example, "database design" is recorded
    instead of both "database" and "design" when both appear.
    """
    seen: set[str] = set()
    matched: list[str] = []
    reasons: list[str] = []

    for kw in sorted(keywords, key=len, reverse=True):
        if kw in text and kw not in seen:
            matched.append(kw)
            seen.add(kw)
            reasons.append(f'"{kw}"')

    return matched, reasons
