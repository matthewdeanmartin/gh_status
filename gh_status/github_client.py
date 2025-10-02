# gh_status/github_client.py
from __future__ import annotations

import logging
from typing import Any, List, Optional

import httpx
from hishel import CacheClient

from . import schemas

logger = logging.getLogger(__name__)

API_URL = "https://api.github.com"


class GitHubClient:
    """A client for fetching public data from the GitHub API, with caching."""

    def __init__(self, username: str, token: str):
        """
        Initializes the GitHub client.

        Args:
            username: The GitHub username to fetch data for.
            token: A GitHub token for authentication.
        """
        self.username = username
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # hishel wraps httpx to provide RFC 9111 compliant caching.
        # It automatically handles ETags and Cache-Control headers.
        self.client: CacheClient | None = CacheClient(headers=headers)

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _get_paginated(self, url: str) -> List[dict[str, Any]]:
        """Handles pagination for a GitHub API GET request."""
        if not self.client:
            raise RuntimeError("Client is not initialized or has been closed.")

        items = []
        try:
            response = self.client.get(url)
            response.raise_for_status()
            items.extend(response.json())

            while "next" in response.links:
                next_url = response.links["next"]["url"]
                logger.info("Fetching next page: %s", next_url)
                response = self.client.get(next_url)
                response.raise_for_status()
                items.extend(response.json())

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error during paginated fetch for %s: %s", url, e)
        return items

    def get_public_repos(self) -> List[schemas.RepoInventoryItem]:
        """Fetches all public repositories for the user."""
        logger.info("Fetching public repositories for %s...", self.username)
        url = f"{API_URL}/users/{self.username}/repos?type=public&per_page=100"
        repo_data = self._get_paginated(url)

        repos = []
        for item in repo_data:
            if item.get("archived"):
                continue
            repos.append(
                schemas.RepoInventoryItem(
                    full=item["full_name"],
                    desc=item.get("description"),
                    topics=item.get("topics", []),
                    lang=item.get("language"),
                    stars=item.get("stargazers_count", 0),
                    forks=item.get("forks_count", 0),
                    open_issues=item.get("open_issues_count", 0),
                    pushed_utc=item["pushed_at"],
                    homepage=item.get("homepage"),
                    default_branch=item["default_branch"],
                )
            )

        logger.info("Found %d public repositories.", len(repos))
        return sorted(repos, key=lambda r: r.pushed_utc, reverse=True)

    def get_public_events(self) -> List[dict[str, Any]]:
        """Fetches recent public events for the user."""
        if not self.client:
            raise RuntimeError("Client is not initialized or has been closed.")

        logger.info("Fetching public events for %s...", self.username)
        url = f"{API_URL}/users/{self.username}/events/public?per_page=100"
        return self._get_paginated(url)

    def get_file_content(self, repo_full_name: str, file_path: str) -> Optional[str]:
        """
        Fetches the content of a specific file from a repository.
        Returns None if the file is not found.
        """
        if not self.client:
            raise RuntimeError("Client is not initialized or has been closed.")

        url = f"{API_URL}/repos/{repo_full_name}/contents/{file_path}"
        try:
            # Use a specific header to get raw content directly
            headers = {"Accept": "application/vnd.github.raw"}
            response = self.client.get(url, headers=headers)

            if response.status_code == 404:
                logger.debug("File not found: %s in %s", file_path, repo_full_name)
                return None
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.warning("Could not fetch file %s from %s: %s", file_path, repo_full_name, e)
            return None

    def get_recent_file_changes(self, repo_full_name: str) -> Optional[List[str]]:
        """
        Gets a list of all file paths from the latest commit's tree.
        This is for the detailed summary of "hot" repos.
        """
        if not self.client:
            raise RuntimeError("Client is not initialized or has been closed.")

        commits_url = f"{API_URL}/repos/{repo_full_name}/commits"
        try:
            # Get the SHA of the latest commit on the default branch
            response = self.client.get(commits_url, params={"per_page": 1})
            response.raise_for_status()
            latest_commit = response.json()[0]
            commit_sha = latest_commit["sha"]

            # Get the full commit tree recursively
            tree_url = f"{API_URL}/repos/{repo_full_name}/git/trees/{commit_sha}?recursive=1"
            tree_response = self.client.get(tree_url)
            tree_response.raise_for_status()

            tree_data = tree_response.json()
            if tree_data.get("truncated"):
                logger.warning("Commit tree for %s was truncated.", repo_full_name)

            # Return a list of file paths (type: "blob")
            return [item["path"] for item in tree_data.get("tree", []) if item.get("type") == "blob"]

        except (httpx.HTTPStatusError, IndexError, KeyError) as e:
            logger.error("Could not fetch recent file changes for %s: %s", repo_full_name, e)
            return None

    def close(self):
        """Closes the underlying httpx client if it exists."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("GitHub client closed.")