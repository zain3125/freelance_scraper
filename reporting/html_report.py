"""Generate a self-contained HTML report from scored projects."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

from models import Project
from ranking.scorer import ProjectScore

REPORT_PATH = Path(__file__).resolve().parent.parent / "report.html"


# ── Public API ──────────────────────────────────────────────────────────


def generate_report(
    scored_projects: list[tuple[Project, ProjectScore]],
    total_collected: int,
) -> Path:
    """Write the HTML report and return its path."""
    accepted = [ps for ps in scored_projects if ps[1].accepted]
    accepted.sort(key=lambda ps: ps[1].score, reverse=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = _render(now, total_collected, accepted)
    REPORT_PATH.write_text(html, encoding="utf-8")
    return REPORT_PATH


# ── Rendering ───────────────────────────────────────────────────────────


def _render(
    now: str,
    total_collected: int,
    accepted: list[tuple[Project, ProjectScore]],
) -> str:
    cards = "\n".join(_project_card(p, s) for p, s in accepted)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freelance Report – {now}</title>
{_STYLE}
</head>
<body>

<header>
  <h1>Daily Freelance Report</h1>
  <div class="meta">
    <span>{now}</span>
    <span>{total_collected} collected</span>
    <span>{len(accepted)} accepted</span>
  </div>
</header>

<main>
{_empty_state(accepted) if not accepted else cards}
</main>

</body>
</html>"""


def _empty_state(accepted: list[tuple[Project, ProjectScore]]) -> str:
    if accepted:
        return ""
    return (
        '<div class="empty">'
        "<h2>No matching projects found today</h2>"
        "<p>Try adjusting the skill filters or ranking rules.</p>"
        "</div>"
    )


def _project_card(project: Project, score: ProjectScore) -> str:
    tags = _keyword_tags(score.matched_keywords, score.rejected_keywords)
    budget_row = ""
    if project.budget:
        budget_row = f'<span class="budget">{escape(project.budget)}</span>'
    date_row = ""
    if project.published_at:
        date_row = f'<span class="date">{escape(project.published_at)}</span>'
    client_row = ""
    if project.client:
        client_row = f'<span class="client">{escape(project.client)}</span>'

    return f"""
<article>
  <div class="card-header">
    <span class="score badge-{_score_color(score.score)}">{score.score}</span>
    <h2><a href="{escape(project.url)}" target="_blank" rel="noopener">{escape(project.title)}</a></h2>
  </div>
  <div class="card-meta">
    <span class="site">{escape(project.site)}</span>
    {budget_row}
    {date_row}
    {client_row}
  </div>
  <p class="desc">{escape(project.description)}</p>
  {tags}
  <form method="POST" action="/ignore/{escape(project.site)}/{escape(project.id)}" class="ignore-form">
    <button type="submit" class="btn-ignore">Ignore</button>
  </form>
</article>"""


def _keyword_tags(
    matched: list[str], rejected: list[str]
) -> str:
    parts: list[str] = []
    if matched:
        parts.append(
            '<div class="keywords positive">'
            + "".join(f"<span>+{escape(k)}</span>" for k in matched)
            + "</div>"
        )
    if rejected:
        parts.append(
            '<div class="keywords negative">'
            + "".join(f"<span>&minus;{escape(k)}</span>" for k in rejected)
            + "</div>"
        )
    return "\n".join(parts)


def _score_color(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "mid"
    return "low"


# ── Embedded CSS ────────────────────────────────────────────────────────

_STYLE = """<style>
:root {
  --bg: #f5f6f8;
  --card: #ffffff;
  --border: #e0e3e8;
  --text: #1a1a2e;
  --muted: #6b7280;
  --green: #16a34a;
  --yellow: #ca8a04;
  --red: #dc2626;
  --blue: #2563eb;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  padding: 1.5rem;
  max-width: 960px;
  margin: 0 auto;
}
header { margin-bottom: 2rem; }
header h1 { font-size: 1.5rem; margin-bottom: .25rem; }
.meta { display:flex; gap:1rem; flex-wrap:wrap; color:var(--muted); font-size:.875rem; }
.meta span { background:#e5e7eb; padding:.15rem .5rem; border-radius:4px; }
article {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.card-header { display:flex; align-items:flex-start; gap:.75rem; margin-bottom:.5rem; }
.card-header h2 { font-size:1rem; font-weight:600; }
.card-header h2 a { color:var(--blue); text-decoration:none; }
.card-header h2 a:hover { text-decoration:underline; }
.badge {
  display:inline-flex; align-items:center; justify-content:center;
  min-width:2.5rem; height:1.75rem;
  font-weight:700; font-size:.8rem; color:#fff;
  border-radius:4px; flex-shrink:0;
}
.badge-high { background:var(--green); }
.badge-mid  { background:var(--yellow); }
.badge-low  { background:var(--red); }
.card-meta { display:flex; gap:.75rem; flex-wrap:wrap; font-size:.8rem; color:var(--muted); margin-bottom:.5rem; }
.desc { font-size:.875rem; color:#374151; margin-bottom:.5rem; }
.keywords { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.25rem; }
.keywords span {
  font-size:.75rem; padding:.15rem .45rem;
  border-radius:3px; font-family:monospace;
}
.keywords.positive span { background:#dcfce7; color:#166534; }
.keywords.negative span { background:#fee2e2; color:#991b1b; }
.ignore-form { margin-top:.75rem; }
.btn-ignore {
  background:none; border:1px solid #d1d5db; color:var(--muted);
  padding:.25rem .75rem; border-radius:4px; font-size:.8rem; cursor:pointer;
}
.btn-ignore:hover { border-color:var(--red); color:var(--red); }
.empty { text-align:center; padding:4rem 1rem; color:var(--muted); }
.empty h2 { margin-bottom:.5rem; color:var(--text); }
@media (max-width:640px) {
  body { padding:.75rem; }
  .card-header { flex-direction:column; gap:.25rem; }
}
</style>"""
