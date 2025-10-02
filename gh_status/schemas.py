# gh_status/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# --- Inventory Schemas ---

class RepoInventoryItem(BaseModel):
    # Core Fields
    full: str
    desc: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    lang: Optional[str] = None
    stars: int
    forks: int
    open_issues: int
    pushed_utc: datetime
    homepage: Optional[str] = None
    default_branch: str

    # Detailed Fields for "Hot" Repos
    readme: Optional[str] = Field(None, description="The full content of the README file.")
    changelog: Optional[str] = Field(None, description="The full content of the changelog file.")
    recent_files: Optional[List[str]] = Field(None, description="A list of files changed in recent commits.")

class Inventory(BaseModel):
    schema_version: str = "1"
    username: str
    generated_utc: datetime
    repo: List[RepoInventoryItem] = Field(default_factory=list)


# --- TODOs Schemas ---

class RepoTodosItem(BaseModel):
    full: str
    todos: Optional[List[str]] = None
    synopsis: Optional[List[str]] = None

class Todos(BaseModel):
    schema_version: str = "1"
    username: str
    generated_utc: datetime
    repo: List[RepoTodosItem] = Field(default_factory=list)


# --- Activity Schemas ---

class ActivitySummary(BaseModel):
    events: int = 0
    repos: int = 0
    pushes: int = 0
    pull_requests: int = 0
    issues: int = 0
    comments: int = 0
    releases: int = 0
    stars: int = 0
    creates: int = 0
    deletes: int = 0

class ActivityInsights(BaseModel):
    streak_days: int
    busiest_local_day: Optional[str] = None
    top_repos: List[str]
    top_event_types: List[str]

class ActivityEvent(BaseModel):
    type: str
    repo_owner: str
    repo_name: str
    at_utc: datetime
    url: str
    title: str
    commits: Optional[List[str]] = None
    event_id: str

class Activity(BaseModel):
    schema_version: str = "1"
    username: str
    generated_utc: datetime
    window_start_utc: datetime
    window_days: int
    summary: ActivitySummary
    insights: ActivityInsights
    event: List[ActivityEvent] = Field(default_factory=list)

# --- Hints Schema (Optional) ---
class HintsSuggest(BaseModel):
    queries: List[str] = Field(default_factory=list)

class HintsContext(BaseModel):
    recent_keywords: List[str] = Field(default_factory=list)
    focus_repos: List[str] = Field(default_factory=list)

class Hints(BaseModel):
    schema_version: str = "1"
    generated_utc: datetime
    suggest: HintsSuggest
    context: HintsContext