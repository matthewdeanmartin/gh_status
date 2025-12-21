# gh_status

Generate **LLM-optimized, machine-readable public GitHub activity feeds** (inventory, TODOs, and recent activity) on a fixed daily schedule.

Outputs are **TOML + safe HTML wrappers**, suitable for:

* static hosting (e.g. GitHub Pages),
* ingestion by LLMs,
* downstream automation or dashboards.

---

## What This Does (High-Level)

On execution, `gh_status`:

1. Fetches **all public, non-archived repositories** for a GitHub user.
2. Identifies the **most recently active repositories** (“hot repos”).
3. Builds three datasets:

   * **Repository inventory**
   * **Aggregated TODOs**
   * **Recent public activity (7-day and 30-day windows)**
4. Serializes each dataset to **TOML**, plus a minimal **HTML wrapper** for human inspection.
5. Writes results to a target directory (default: `docs/`).

Execution is **time-gated** to avoid unnecessary API usage.

---

## Outputs

By default, the following files are generated:

```text
docs/
├── inventory.toml
├── inventory.toml.html
├── todos.toml
├── todos.toml.html
├── latest-7d.toml
├── latest-7d.toml.html
├── latest-30d.toml
└── latest-30d.toml.html
```

All TOML files conform to explicit Pydantic schemas (`schemas.py`).

---

## Data Products

### 1. Inventory (`inventory.toml`)

Per-repository metadata:

* name, description, language
* stars, forks, open issues
* last push timestamp
* topics, homepage, default branch

For the **N most recently pushed repos** (`HOT_REPO_COUNT = 3`):

* full `README.md`
* full `CHANGELOG.md` (if present)
* full file list from latest commit tree

Purpose: **state snapshot** of public work.

---

### 2. TODOs (`todos.toml`)

For each repository:

* Extracts TODO items from:

  * `docs/TODO.md` (currently enabled)
* Normalizes lines (markdown stripped)
* Extracts a short **synopsis** from the README (first non-header lines)

Purpose: **cross-repo task surface**.

---

### 3. Activity Feeds (`latest-7d.toml`, `latest-30d.toml`)

Derived from GitHub **public events**:

* Pushes
* PRs
* Issues
* Comments
* Releases
* Stars
* Repo creates / deletes

Includes:

* **Summary counts**
* **Insights**

  * activity streak (local-timezone aware)
  * busiest day
  * top repos
  * top event types
* **Event-level detail**

  * titles
  * URLs
  * commit summaries (for pushes)

Purpose: **recent behavioral signal**, not a full audit log.

---

## Execution Model

### Time Guard

By default, execution only occurs when:

* Local time (configured timezone) is **17:00 (5 PM)**

Override with:

```bash
--force
```

Rationale: deterministic daily snapshots + API restraint.

---

## Configuration

### Environment Variables

Required:

```bash
GITHUB_USERNAME=your_username
GITHUB_TOKEN=your_token
```

Optional:

```bash
TZ_NAME=America/New_York   # default
```

`.env` files are supported.

---

## CLI Usage

```bash
python -m gh_status [options]
```

### Options

| Flag           | Description                         |
| -------------- | ----------------------------------- |
| `--username`   | GitHub username (overrides env)     |
| `--token`      | GitHub token (overrides env)        |
| `--output-dir` | Output directory (default: `docs/`) |
| `--force`      | Ignore time guard                   |

Exit codes:

* `0` → success or intentional skip
* `1` → configuration or runtime failure

---

## Architecture Notes

### Key Modules

| Module                          | Responsibility                              |
| ------------------------------- | ------------------------------------------- |
| `cli.py`                        | Argument parsing, scheduling, orchestration |
| `builder.py`                    | Data assembly and transformation            |
| `github_client.py`              | Cached GitHub API access                    |
| `schemas.py`                    | Canonical data contracts (Pydantic)         |
| `writers.py`                    | TOML + HTML serialization                   |
| `resources/wrapper.html.jinja2` | Safe HTML viewer                            |

---

## GitHub API Strategy

* Uses **`hishel` + `httpx`** for RFC-compliant caching
* Handles pagination
* Fetches raw file contents when needed
* Avoids archived repositories
* Fails soft on missing files (e.g. TODOs, changelogs)

---

## Intended Use Cases

* Public developer status page
* LLM context bootstrap
* Personal activity telemetry
* Static “what am I working on?” feeds
* Input layer for downstream summarizers or agents

Not intended to:

* Replace GitHub analytics
* Track private activity
* Provide real-time updates

---

## Assumptions & Limits

* Public data only
* GitHub event history is truncated by GitHub itself
* Activity windows are bounded by available events
* TODO discovery is opinionated and conservative
* Schema versioning is manual (`schema_version = "1"`)

---

## If You’re Extending This

Low-risk extension points:

* Enable more TODO sources
* Add hint generation (`Hints` schema already stubbed)
* Emit JSON alongside TOML
* Add repo filtering rules
* Add cron / GitHub Actions wrapper