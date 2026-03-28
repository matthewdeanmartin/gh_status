# gh_status/writers.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import tomlkit
from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Set up the Jinja2 environment to load templates from our package's 'resources' folder.
# This works for both local development and installed packages.
jinja_env = Environment(
    loader=PackageLoader("gh_status", "resources"),
    autoescape=select_autoescape(["html", "xml"])
)


def _describe_feed(title: str) -> tuple[str, str]:
    lowered = title.lower()
    if lowered.startswith("inventory"):
        return (
            "Repository Inventory",
            "A machine-readable inventory of public repositories, including detailed context for the freshest projects.",
        )
    if lowered.startswith("todos"):
        return (
            "Aggregated TODOs",
            "A cross-repo planning surface assembled from public TODO files and README summaries.",
        )
    if lowered.startswith("latest-7d"):
        return (
            "Recent Activity: 7 Days",
            "A short-window activity feed intended to show current momentum and near-term movement.",
        )
    if lowered.startswith("latest-30d"):
        return (
            "Recent Activity: 30 Days",
            "A broader public activity feed with enough history to reveal patterns, streaks, and top repositories.",
        )
    return (
        title,
        "A generated TOML feed rendered in an HTML reading view.",
    )


def write_toml(path: Path, data: BaseModel) -> None:
    """
    Serializes a Pydantic model to a TOML file using tomlkit.

    Args:
        path: The destination file path (e.g., docs/inventory.toml).
        data: The Pydantic model instance to write.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        data_dict = data.model_dump(mode='json',exclude_none=True)
        toml_content = tomlkit.dumps(data_dict)

        path.write_text(toml_content, encoding="utf-8")
        logger.info("Successfully wrote TOML file to %s", path)
    except Exception as e:
        logger.error("Failed to write TOML file to %s: %s", path, e)


def write_json(path: Path, data: BaseModel | dict[str, Any]) -> None:
    """
    Serializes a Pydantic model or plain dictionary to a JSON file.

    Args:
        path: The destination file path (e.g., docs/inventory.json).
        data: The data structure to write.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = data.model_dump(mode="json", exclude_none=True) if isinstance(data, BaseModel) else data
        path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
        logger.info("Successfully wrote JSON file to %s", path)
    except Exception as e:
        logger.error("Failed to write JSON file to %s: %s", path, e)
        raise


def write_html_wrapper(toml_path: Path) -> None:
    """
    Creates a safely-rendered HTML wrapper for an existing TOML file using a Jinja2 template.

    Args:
        toml_path: The path to the source .toml file.
    """
    html_path = toml_path.with_suffix(toml_path.suffix + ".html")
    try:
        template = jinja_env.get_template("wrapper.html.jinja2")
        toml_content = toml_path.read_text(encoding="utf-8")
        heading, description = _describe_feed(toml_path.name)

        html_content = template.render(
            title=toml_path.name,
            heading=heading,
            description=description,
            source_name=toml_path.name,
            line_count=len(toml_content.splitlines()),
            content=toml_content,
        )

        html_path.write_text(html_content, encoding="utf-8")
        logger.info("Successfully wrote HTML wrapper to %s", html_path)
    except FileNotFoundError:
        logger.error("Cannot create HTML wrapper: source file %s not found.", toml_path)
    except Exception as e:
        logger.error("Failed to write HTML wrapper to %s: %s", html_path, e)
        raise


def write_dashboard(
    output_dir: Path,
    *,
    inventory: BaseModel,
    todos: BaseModel,
    activity_7d: BaseModel,
    activity_30d: BaseModel,
    build_info: dict[str, Any],
) -> None:
    """
    Writes the static dashboard landing page for GitHub Pages.

    Args:
        output_dir: Directory containing the generated feed files.
        inventory: Inventory model instance.
        todos: Todos model instance.
        activity_7d: Seven-day activity model instance.
        activity_30d: Thirty-day activity model instance.
        build_info: Metadata about the current build and publish context.
    """
    try:
        template = jinja_env.get_template("dashboard.html.jinja2")
        output_dir.mkdir(parents=True, exist_ok=True)
        dashboard_path = output_dir / "index.html"

        repos = list(getattr(inventory, "repo", []))
        todo_repos = list(getattr(todos, "repo", []))
        hot_repos = repos[:3]

        todo_items = sum(len(repo.todos or []) for repo in todo_repos)
        repos_with_todos = sum(1 for repo in todo_repos if repo.todos)

        stats = [
            {
                "label": "Public repos",
                "value": len(repos),
                "detail": "Non-archived repositories scanned",
            },
            {
                "label": "TODO items",
                "value": todo_items,
                "detail": f"Across {repos_with_todos} repos",
            },
            {
                "label": "Events (7d)",
                "value": activity_7d.summary.events,
                "detail": f"{activity_7d.summary.pushes} pushes, {activity_7d.summary.pull_requests} PRs",
            },
            {
                "label": "Events (30d)",
                "value": activity_30d.summary.events,
                "detail": f"Across {activity_30d.summary.repos} repos",
            },
        ]

        chart_values = [
            ("Pushes", activity_30d.summary.pushes),
            ("Pull requests", activity_30d.summary.pull_requests),
            ("Issues", activity_30d.summary.issues),
            ("Comments", activity_30d.summary.comments),
            ("Releases", activity_30d.summary.releases),
            ("Stars", activity_30d.summary.stars),
        ]
        chart_max = max((value for _, value in chart_values), default=1) or 1
        activity_chart = [
            {
                "label": label,
                "value": value,
                "width_pct": max(8, round((value / chart_max) * 100)) if value else 8,
            }
            for label, value in chart_values
        ]

        hot_repo_cards = []
        warnings = list(build_info.get("warnings", []))
        for repo in hot_repos:
            todo_entry = next((item for item in todo_repos if item.full == repo.full), None)
            todo_count = len(todo_entry.todos or []) if todo_entry else 0
            synopsis = (todo_entry.synopsis or [])[:2] if todo_entry else []
            recent_files = (repo.recent_files or [])[:5]

            if not repo.readme:
                warnings.append(f"Hot repo {repo.full} is missing README.md content.")
            if not repo.recent_files:
                warnings.append(f"Hot repo {repo.full} is missing recent file change data.")

            hot_repo_cards.append(
                {
                    "full": repo.full,
                    "url": f"https://github.com/{repo.full}",
                    "description": repo.desc or "No description provided.",
                    "language": repo.lang or "Unknown",
                    "stars": repo.stars,
                    "forks": repo.forks,
                    "open_issues": repo.open_issues,
                    "pushed_utc": repo.pushed_utc,
                    "todo_count": todo_count,
                    "synopsis": synopsis,
                    "recent_files": recent_files,
                }
            )

        if not todo_items:
            warnings.append("No TODO items were extracted from public repositories.")
        if not activity_7d.summary.events:
            warnings.append("No public GitHub events were found in the last 7 days.")
        if not build_info.get("commit_sha"):
            warnings.append("Commit SHA was not provided to the build environment.")

        links = [
            {
                "label": "Inventory",
                "toml": "inventory.toml",
                "html": "inventory.toml.html",
                "json": "inventory.json",
            },
            {
                "label": "TODOs",
                "toml": "todos.toml",
                "html": "todos.toml.html",
                "json": "todos.json",
            },
            {
                "label": "Latest 7 days",
                "toml": "latest-7d.toml",
                "html": "latest-7d.toml.html",
                "json": "latest-7d.json",
            },
            {
                "label": "Latest 30 days",
                "toml": "latest-30d.toml",
                "html": "latest-30d.toml.html",
                "json": "latest-30d.json",
            },
        ]

        html_content = template.render(
            username=getattr(inventory, "username", "unknown"),
            generated_utc=getattr(inventory, "generated_utc", None),
            stats=stats,
            activity_chart=activity_chart,
            hot_repos=hot_repo_cards,
            links=links,
            build_info=build_info,
            warnings=warnings,
            top_repos_30d=list(activity_30d.insights.top_repos),
            busiest_day=activity_30d.insights.busiest_local_day,
            streak_days=activity_30d.insights.streak_days,
            bootstrap={
                "username": getattr(inventory, "username", "unknown"),
                "generated_utc": str(getattr(inventory, "generated_utc", "")),
                "build_info": build_info,
                "links": links,
            },
        )

        dashboard_path.write_text(html_content, encoding="utf-8")
        logger.info("Successfully wrote dashboard to %s", dashboard_path)
    except Exception as e:
        logger.error("Failed to write dashboard to %s: %s", output_dir / "index.html", e)
        raise
