# cf-ip-access-sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS Python CLI that keeps the current public laptop IP synced to a Cloudflare account-level IP Access Rule using `mode = "whitelist"`.

**Architecture:** The CLI is split into focused modules: config and Keychain token handling, public IP detection, Cloudflare API access, sync rule selection, LaunchAgent plist generation, and command parsing. Sync logic never modifies or deletes a Cloudflare rule unless the rule note contains the exact managed marker for the selected profile and IP family.

**Tech Stack:** Python 3.11+, standard library runtime, `pytest` for tests.

---

### Task 1: Test Safety Boundaries

**Files:**
- Create: `tests/test_ip_detect.py`
- Create: `tests/test_rule_selection.py`
- Create: `tests/test_cloudflare_payloads.py`
- Create: `tests/test_launchd_plist.py`

- [ ] Write tests for IP validation, resolver family enforcement, exact marker selection, duplicate cleanup, dry-run behavior, payload generation, and LaunchAgent plist fields.
- [ ] Run `PYTHONPATH=src python3 -m pytest -q` and confirm the suite fails because modules are not implemented yet.

### Task 2: Implement Core Modules

**Files:**
- Create: `src/cf_ip_access_sync/config.py`
- Create: `src/cf_ip_access_sync/ip_detect.py`
- Create: `src/cf_ip_access_sync/cloudflare.py`
- Create: `src/cf_ip_access_sync/keychain.py`
- Create: `src/cf_ip_access_sync/sync.py`
- Create: `src/cf_ip_access_sync/launchd.py`
- Create: `src/cf_ip_access_sync/logging_utils.py`
- Create: `src/cf_ip_access_sync/cli.py`
- Create: `src/cf_ip_access_sync/__main__.py`
- Create: `src/cf_ip_access_sync/__init__.py`

- [ ] Add dataclasses and helpers for config, Cloudflare rules, sync results, LaunchAgent plist creation, and public IP validation.
- [ ] Implement Cloudflare account-level IP Access Rules API calls with pagination and safe error messages.
- [ ] Implement sync selection so only exact managed marker rules are patched or deleted.
- [ ] Implement macOS Keychain storage using Security.framework through `ctypes`, with `CLOUDFLARE_API_TOKEN` taking precedence.
- [ ] Implement CLI commands: `configure`, `sync`, `status`, `install-agent`, `uninstall-agent`, and `remove-managed-rule`.

### Task 3: Verify and Package

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`

- [ ] Run `PYTHONPATH=src python3 -m pytest -q`.
- [ ] Run `python3 -m compileall src`.
- [ ] Initialize git, commit the project, create the GitHub repository, and push it.
