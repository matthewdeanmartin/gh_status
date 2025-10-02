# gh_status/builder.py
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import List

import pytz

from . import github_client, schemas

logger = logging.getLogger(__name__)

# Define how many of the top repos are considered "hot" to fetch detailed content for.
HOT_REPO_COUNT = 3


# --- Helper Functions ---

def _normalize_todo_line(line: str) -> str:
    """Strips markdown list markers, extra whitespace, and truncates the line."""
    # Remove markdown list prefixes like *, -, [ ], [x]
    line = re.sub(r"^\s*[-*]\s*(\[[ xX]\])?\s*", "", line)
    return line.strip()


def _parse_todos_from_content(content: str) -> List[str]:
    """Extracts and normalizes TODO lines from a markdown file's content."""
    todos = []
    for line in content.splitlines():
        normalized = _normalize_todo_line(line)
        if normalized:
            todos.append(normalized)
    return todos


# --- Builder Functions ---

def build_inventory(client: github_client.GitHubClient, username: str) -> schemas.Inventory:
    """
    Builds the repository inventory, including detailed content for "hot" repos.
    """
    repos = client.get_public_repos()

    # Identify the top N most recently pushed repos as "hot"
    hot_repo_names = {repo.full for repo in repos[:HOT_REPO_COUNT]}
    logger.info("Identified hot repos for detailed summary: %s", hot_repo_names)

    for repo in repos:
        if repo.full in hot_repo_names:
            logger.info("Fetching details for hot repo: %s", repo.full)
            # Fetch detailed content
            repo.readme = client.get_file_content(repo.full, "README.md")
            repo.changelog = client.get_file_content(repo.full, "CHANGELOG.md")
            repo.recent_files = client.get_recent_file_changes(repo.full)

    return schemas.Inventory(
        username=username,
        generated_utc=datetime.utcnow(),
        repo=repos
    )


def build_todos(client: github_client.GitHubClient, inventory: schemas.Inventory) -> schemas.Todos:
    """
    Builds the aggregated TODO list by fetching content from each repository.
    """
    repo_todos_list = []

    # Files to check for TODOs, in order of preference
    todo_filenames = ["docs/TODO.md", "TODO.md", "todo.md", "docs/ROADMAP.md"]

    for repo in inventory.repo:
        repo_todos = schemas.RepoTodosItem(full=repo.full)

        # 1. Look for a TODO file
        todo_content = None
        for filename in todo_filenames:
            content = client.get_file_content(repo.full, filename)
            if content:
                logger.info("Found TODOs for %s in %s", repo.full, filename)
                todo_content = content
                break

        if todo_content:
            repo_todos.todos = _parse_todos_from_content(todo_content)

        # 2. Get synopsis from README
        readme_content = repo.readme or client.get_file_content(repo.full, "README.md")
        if readme_content:
            # Extract first few non-empty lines as synopsis
            synopsis_lines = [
                line.strip() for line in readme_content.strip().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ][:5]  # Cap at 5 lines
            repo_todos.synopsis = synopsis_lines

        repo_todos_list.append(repo_todos)

    return schemas.Todos(
        username=inventory.username,
        generated_utc=datetime.utcnow(),
        repo=repo_todos_list
    )


def build_activity(
        client: github_client.GitHubClient,
        username: str,
        tz_name: str,
        window_days: int
) -> schemas.Activity:
    """Builds the activity feed for a given time window (e.g., 7 or 30 days)."""
    now_utc = datetime.utcnow()
    window_start_utc = now_utc - timedelta(days=window_days)
    local_tz = pytz.timezone(tz_name)

    all_events = client.get_public_events()

    # Filter events within the window
    window_events = [
        e for e in all_events
        if datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")) >= window_start_utc
    ]

    # --- Calculate Summary and Insights ---
    repo_counter = Counter(e["repo"]["name"] for e in window_events)
    type_counter = Counter(e["type"] for e in window_events)

    # Busiest day and streak
    events_by_local_day = Counter()
    for event in window_events:
        event_time_utc = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
        local_day = event_time_utc.astimezone(local_tz).strftime("%Y-%m-%d")
        events_by_local_day[local_day] += 1

    busiest_day = events_by_local_day.most_common(1)[0][0] if events_by_local_day else None

    # Calculate streak
    active_days = sorted(events_by_local_day.keys())
    streak = 0
    if active_days:
        streak = 1
        # Check consecutive days backwards from the last active day
        current_day = datetime.strptime(active_days[-1], "%Y-%m-%d").date()
        for i in range(len(active_days) - 2, -1, -1):
            prev_day = datetime.strptime(active_days[i], "%Y-%m-%d").date()
            if current_day - prev_day == timedelta(days=1):
                streak += 1
                current_day = prev_day
            else:
                break

    # --- Assemble Pydantic Models ---
    summary = schemas.ActivitySummary(
        events=len(window_events),
        repos=len(repo_counter),
        pushes=type_counter.get("PushEvent", 0),
        pull_requests=type_counter.get("PullRequestEvent", 0),
        issues=type_counter.get("IssuesEvent", 0),
        comments=type_counter.get("IssueCommentEvent", 0) + type_counter.get("CommitCommentEvent", 0),
        releases=type_counter.get("ReleaseEvent", 0),
        stars=type_counter.get("WatchEvent", 0),
        creates=type_counter.get("CreateEvent", 0),
        deletes=type_counter.get("DeleteEvent", 0),
    )

    insights = schemas.ActivityInsights(
        streak_days=streak,
        busiest_local_day=busiest_day,
        top_repos=[f"{name}:{count}" for name, count in repo_counter.most_common(5)],
        top_event_types=[f"{name}:{count}" for name, count in type_counter.most_common(5)],
    )

    events_list = []
    for event in window_events:
        repo_name_full = event["repo"]["name"]
        repo_owner, repo_name_short = repo_name_full.split('/')

        # Simplify payload into a title and optional details
        title = f"{event['type']} on {repo_name_full}"
        commits = None
        url = f"https://github.com/{repo_name_full}"

        if event["type"] == "PushEvent":
            commit_count = event["payload"].get("size", 0)
            plural = "s" if commit_count != 1 else ""
            title = f"Pushed {commit_count} commit{plural} to {repo_name_full}"
            commits = [
                f"{c['sha'][:7]}: {c['message'].splitlines()[0]}"
                for c in event["payload"].get("commits", [])
            ]
            if "ref" in event["payload"]:
                url = f"https://github.com/{repo_name_full}/tree/{event['payload']['ref']}"
        elif event["type"] == "PullRequestEvent":
            action = event["payload"]["action"]
            pr_title = event["payload"]["pull_request"]["title"]
            title = f"PR {action}: \"{pr_title}\" on {repo_name_full}"
            url = event["payload"]["pull_request"]["html_url"]

        events_list.append(schemas.ActivityEvent(
            type=event["type"],
            repo_owner=repo_owner,
            repo_name=repo_name_short,
            at_utc=event["created_at"],
            url=url,
            title=title,
            commits=commits,
            event_id=event["id"]
        ))

    return schemas.Activity(
        username=username,
        generated_utc=now_utc,
        window_start_utc=window_start_utc,
        window_days=window_days,
        summary=summary,
        insights=insights,
        event=events_list
    )