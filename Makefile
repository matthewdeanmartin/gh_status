# Makefile for gh_status
#
# Purpose:
# - Run gh_status (time-gated unless FORCE=1)
# - Generate TOML + HTML wrappers into OUTPUT_DIR (default: docs/)
# - Provide convenience targets for .env validation and cleanup
#
# Assumptions:
# - You run in a Python environment where `gh_status` deps are installed.
# - Config comes from .env and/or exported env vars:
#     GITHUB_USERNAME, GITHUB_TOKEN, optional TZ_NAME
#
# Usage examples:
#   make status
#   make status FORCE=1
#   make status OUTPUT_DIR=public
#   make clean
#   make check-env

# SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

PY ?= python
MODULE := gh_status

OUTPUT_DIR ?= docs
TZ_NAME ?= America/New_York

# If FORCE=1, we pass --force to bypass the 17:00 local time guard.
FORCE ?= 0

ifeq ($(FORCE),1)
FORCE_FLAG := --force
else
FORCE_FLAG :=
endif

.DEFAULT_GOAL := help

#.PHONY: help
#help:
#	@cat <<'EOF'
#	Targets:
#	  make status            Run gh_status (time-gated unless FORCE=1)
#	  make status FORCE=1    Force run regardless of local hour
#	  make check-env         Verify required environment variables exist
#	  make show-config       Print effective config
#	  make clean             Remove generated TOML and HTML wrapper files
#	  make nuke              Remove entire output directory (OUTPUT_DIR)
#
#	Variables:
#	  OUTPUT_DIR=<dir>       Output directory (default: docs)
#	  TZ_NAME=<tz>           Local timezone name (default: America/New_York)
#	  FORCE=1                Bypass time guard (passes --force)
#
#	Required env vars (via shell export or .env):
#	  GITHUB_USERNAME, GITHUB_TOKEN
#	Optional:
#	  TZ_NAME
#
#	'EOF'

.PHONY: check-env
check-env:
	@missing=0; \
	for v in GITHUB_USERNAME GITHUB_TOKEN; do \
		if [[ -z "$${!v:-}" ]]; then \
			echo "Missing required env var: $$v" >&2; \
			missing=1; \
		fi; \
	done; \
	if [[ $$missing -ne 0 ]]; then \
		echo "" >&2; \
		echo "Set env vars or create a .env file with:" >&2; \
		echo "  GITHUB_USERNAME=..." >&2; \
		echo "  GITHUB_TOKEN=..." >&2; \
		exit 1; \
	fi

.PHONY: show-config
show-config:
	@echo "PY=$(PY)"
	@echo "MODULE=$(MODULE)"
	@echo "OUTPUT_DIR=$(OUTPUT_DIR)"
	@echo "TZ_NAME=$(TZ_NAME)"
	@echo "FORCE=$(FORCE) ($(FORCE_FLAG))"
	@echo "GITHUB_USERNAME=$${GITHUB_USERNAME:-<unset>}"
	@echo "GITHUB_TOKEN=$${GITHUB_TOKEN:+<set>}$${GITHUB_TOKEN:-<unset>}"

.PHONY: build-web
build-web:
	@npm install
	@npm run build:web

.PHONY: status
status: check-env build-web
	@mkdir -p "$(OUTPUT_DIR)"
	@# The CLI loads .env itself, but we also pass TZ_NAME explicitly for clarity.
	@TZ_NAME="$(TZ_NAME)" $(PY) -m $(MODULE) \
		--output-dir "$(OUTPUT_DIR)" \
		--force

# Remove only the files this tool generates, keep directory.
.PHONY: clean
clean:
	@rm -f \
		"$(OUTPUT_DIR)/inventory.toml" \
		"$(OUTPUT_DIR)/inventory.toml.html" \
		"$(OUTPUT_DIR)/todos.toml" \
		"$(OUTPUT_DIR)/todos.toml.html" \
		"$(OUTPUT_DIR)/latest-7d.toml" \
		"$(OUTPUT_DIR)/latest-7d.toml.html" \
		"$(OUTPUT_DIR)/latest-30d.toml" \
		"$(OUTPUT_DIR)/latest-30d.toml.html"
	@echo "Cleaned generated files in $(OUTPUT_DIR)/"

# Remove output dir entirely.
.PHONY: nuke
nuke:
	@rm -rf "$(OUTPUT_DIR)"
	@echo "Removed directory $(OUTPUT_DIR)/"
