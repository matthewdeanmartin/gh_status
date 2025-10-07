# gh_status/writers.py
from __future__ import annotations

import logging
from pathlib import Path

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

        html_content = template.render(
            title=toml_path.name, content=toml_content
        )

        html_path.write_text(html_content, encoding="utf-8")
        logger.info("Successfully wrote HTML wrapper to %s", html_path)
    except FileNotFoundError:
        logger.error("Cannot create HTML wrapper: source file %s not found.", toml_path)
    except Exception as e:
        logger.error("Failed to write HTML wrapper to %s: %s", html_path, e)
        raise