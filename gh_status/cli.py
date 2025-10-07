# gh_status/cli.py
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

import dotenv
import pytz

from gh_status import builder, github_client, writers
dotenv.load_dotenv()

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- Main Application Logic ---

def main() -> int:
    """Main entrypoint for the gh-status CLI."""
    parser = argparse.ArgumentParser(
        description="Generate daily LLM-optimized public activity feeds from GitHub."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run the script regardless of the current time.",
    )
    parser.add_argument(
        "--username",
        help="GitHub username. Defaults to GITHUB_USERNAME env var.",
    )
    parser.add_argument(
        "--token",
        help="GitHub token. Defaults to GITHUB_TOKEN env var.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default="docs",
        help="The directory to write output files to. Defaults to 'docs/'.",
    )
    args = parser.parse_args()

    # --- Configuration and Environment ---
    username = args.username or os.environ.get("GITHUB_USERNAME")
    token = args.token or os.environ.get("GITHUB_TOKEN")
    tz_name = os.environ.get("TZ_NAME", "America/New_York")

    if not username or not token:
        logger.error(
            "GitHub username and token are required. Set GITHUB_USERNAME and GITHUB_TOKEN environment variables or use flags.")
        return 1

    # --- Time Guard ---
    try:
        local_tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        logger.error("Unknown timezone: %s. Set the TZ_NAME environment variable correctly.", tz_name)
        return 1

    now_local = datetime.now(local_tz)
    if now_local.hour != 17 and not args.force:
        logger.info(
            "Skipping run. Current hour is %d in %s, but required hour is 17. Use --force to override.",
            now_local.hour,
            tz_name,
        )
        return 0

    logger.info("Starting feed generation for user '%s'...", username)

    # --- Orchestration ---
    output_dir = args.output_dir
    output_dir.mkdir(exist_ok=True)

    try:
        with github_client.GitHubClient(username=username, token=token) as client:
            # 1. Build and write Inventory
            logger.info("Building repository inventory...")
            inventory = builder.build_inventory(client, username)
            inventory_path = output_dir / "inventory.toml"
            writers.write_toml(inventory_path, inventory)
            writers.write_html_wrapper(inventory_path)

            # 2. Build and write TODOs
            logger.info("Building aggregated TODOs...")
            todos = builder.build_todos(client, inventory)
            todos_path = output_dir / "todos.toml"
            writers.write_toml(todos_path, todos)
            writers.write_html_wrapper(todos_path)

            # 3. Build and write Activity Feeds
            for days in [7, 30]:
                logger.info("Building %d-day activity feed...", days)
                activity = builder.build_activity(client, username, tz_name, window_days=days)
                activity_path = output_dir / f"latest-{days}d.toml"
                writers.write_toml(activity_path, activity)
                writers.write_html_wrapper(activity_path)
        logger.info("✅ Successfully generated all feeds in '%s'.", output_dir)
        return 0
    except Exception:
        logger.exception("An unhandled error occurred during feed generation.")
        return 1


if __name__ == '__main__':
    main()