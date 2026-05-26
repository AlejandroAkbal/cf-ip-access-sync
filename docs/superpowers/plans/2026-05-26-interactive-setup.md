# Interactive Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive `cf-ip-access-sync setup` command and simplify the README around that first-run path.

**Architecture:** Add a focused `src/cf_ip_access_sync/setup.py` module for interactive prompt parsing, setup answer collection, and setup orchestration. Keep `src/cf_ip_access_sync/cli.py` responsible for argument parsing and command dispatch. Tests cover the prompt helpers and setup orchestration with injected fakes so no real Keychain, Cloudflare, launchd, or terminal interaction is needed.

**Tech Stack:** Python 3.11 standard library, macOS Keychain integration already present in the project, `pytest` for tests.

---

### Task 1: Add Setup Unit Tests

**Files:**
- Create: `tests/test_setup.py`

- [ ] Add tests for default values, yes/no parsing, non-TTY rejection, config construction for IPv4/IPv6, and LaunchAgent skip on dry-run failure.
- [ ] Run: `PYTHONPATH=src python3 -m pytest tests/test_setup.py -q`
- [ ] Expected: tests fail because `cf_ip_access_sync.setup` does not exist yet.

### Task 2: Implement Setup Module

**Files:**
- Create: `src/cf_ip_access_sync/setup.py`

- [ ] Add constants: `DEFAULT_SETUP_PROFILE = "work"`, `DEFAULT_SETUP_INTERVAL_SECONDS = 900`, `TOKEN_DASHBOARD_URL = "https://dash.cloudflare.com/profile/api-tokens"`.
- [ ] Add `SetupAnswers` dataclass with `profile`, `account_id`, `token`, `ip_versions`, `interval_seconds`, and `install_agent`.
- [ ] Add `parse_yes_no(value: str) -> bool | None`.
- [ ] Add prompt helpers that accept injected `input_func`, `secret_func`, and `output`.
- [ ] Add `ensure_interactive(stdin)` that raises a setup error when stdin is not a TTY.
- [ ] Add `collect_setup_answers(...)`.
- [ ] Add `build_profile_config(answers)`.
- [ ] Add `run_setup(...)` that stores the token, saves config, runs status, runs dry-run sync, and only installs the LaunchAgent after a successful dry run and a yes answer.
- [ ] Run: `PYTHONPATH=src python3 -m pytest tests/test_setup.py -q`
- [ ] Expected: setup tests pass.

### Task 3: Wire CLI Command

**Files:**
- Modify: `src/cf_ip_access_sync/cli.py`
- Test: `tests/test_setup.py`

- [ ] Add `setup` parser with `--profile`, `--account-id`, `--interval`, `--ipv6`, and `--no-agent`.
- [ ] Dispatch `setup` to `run_setup`.
- [ ] Include setup-specific errors in the existing expected error handling path.
- [ ] Run: `PYTHONPATH=src python3 -m pytest tests/test_setup.py -q`
- [ ] Expected: setup CLI parser tests pass.

### Task 4: Refresh README

**Files:**
- Modify: `README.md`

- [ ] Rewrite Quick Start so `cf-ip-access-sync setup` is the primary path.
- [ ] Add the suggested Cloudflare token name `cf-ip-access-sync work`.
- [ ] Keep the direct token dashboard URL in the main path.
- [ ] Move extra Cloudflare docs out of the main path and reduce duplicated setup commands.
- [ ] Update interval references from five minutes to fifteen minutes where describing the setup default.

### Task 5: Verify

**Files:**
- No new files.

- [ ] Run: `PYTHONPATH=src python3 -m pytest -q`
- [ ] Expected: all tests pass.
- [ ] Run: `python3 -m compileall src`
- [ ] Expected: compile succeeds.
- [ ] Run: `PYTHONPATH=src python3 -m cf_ip_access_sync --help`
- [ ] Expected: help includes the `setup` subcommand.
- [ ] Run: `PYTHONPATH=src python3 -m cf_ip_access_sync setup < /dev/null`
- [ ] Expected: exits non-zero with a clear non-interactive setup error.
