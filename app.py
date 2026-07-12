"""Local web interface for managing freelance projects.

Usage:
    python app.py

Then open http://localhost:5000
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, redirect, render_template_string, url_for

from database.db import get_active_projects, ignore_project
from models import Project
from ranking.scorer import score_project

app = Flask(__name__)

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freelance Projects</title>
<style>
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
</style>
</head>
<body>
<header>
  <h1>Freelance Projects</h1>
  <div class="meta">
    <span>{{ total }} active</span>
  </div>
</header>
<main>
{% if not projects %}
<div class="empty">
  <h2>No active projects</h2>
  <p>Run <code>python main.py</code> to collect new projects.</p>
</div>
{% endif %}
{% for p in projects %}
<article>
  <div class="card-header">
    <span class="score badge-{{ p.color }}">{{ p.score }}</span>
    <h2><a href="{{ p.url }}" target="_blank" rel="noopener">{{ p.title }}</a></h2>
  </div>
  <div class="card-meta">
    <span class="site">{{ p.site }}</span>
    {% if p.budget %}<span class="budget">{{ p.budget }}</span>{% endif %}
    {% if p.published_at %}<span class="date">{{ p.published_at }}</span>{% endif %}
    {% if p.client %}<span class="client">{{ p.client }}</span>{% endif %}
  </div>
  <p class="desc">{{ p.description }}</p>
  {% if p.matched or p.rejected %}
  <div class="keywords positive">
    {% for k in p.matched %}<span>+{{ k }}</span>{% endfor %}
  </div>
  {% endif %}
  {% if p.rejected %}
  <div class="keywords negative">
    {% for k in p.rejected %}<span>&minus;{{ k }}</span>{% endfor %}
  </div>
  {% endif %}
  <form method="POST" action="/ignore/{{ p.site }}/{{ p.project_id }}" class="ignore-form">
    <button type="submit" class="btn-ignore">Ignore</button>
  </form>
</article>
{% endfor %}
</main>
</body>
</html>"""


def _score_color(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "mid"
    return "low"


@app.get("/")
def index():
    rows = get_active_projects()
    projects = []
    for row in rows:
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
        projects.append({
            "project_id": project.id,
            "site": project.site,
            "title": project.title,
            "url": project.url,
            "description": project.description,
            "budget": project.budget,
            "published_at": project.published_at,
            "client": project.client,
            "score": result.score,
            "color": _score_color(result.score),
            "matched": result.matched_keywords,
            "rejected": result.rejected_keywords,
        })
    return render_template_string(_TEMPLATE, projects=projects, total=len(projects))


@app.post("/ignore/<site>/<project_id>")
def ignore(site: str, project_id: str):
    ignore_project(site, project_id)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
