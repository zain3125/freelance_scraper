from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    id: str
    site: str
    title: str
    description: str
    url: str
    budget: str | None
    skills: list[str]
    published_at: str | None
    client: str | None = None
    category: str | None = None
