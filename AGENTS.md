# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.11+ CLI package. Runtime code lives in `src/cf_ip_access_sync/`.

- `cli.py`: command parsing and command dispatch.
- `setup.py`: interactive first-run setup flow.
- `sync.py`: Cloudflare rule selection and update logic.
- `cloudflare.py`: Cloudflare API client and payload helpers.
- `config.py`, `keychain.py`, `launchd.py`: local config, macOS Keychain, and LaunchAgent support.
- `tests/`: pytest coverage for CLI behavior, sync safety, payloads, IP detection, setup, and launchd plist generation.
- `docs/superpowers/`: design specs and implementation plans.

## Build, Test, and Development Commands

Create a development environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

Run tests:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Compile-check source:

```bash
python3 -m compileall src
```

Run the CLI locally:

```bash
PYTHONPATH=src python3 -m cf_ip_access_sync --help
cf-ip-access-sync sync --profile work --dry-run
cf-ip-access-sync test-agent --profile work
```

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, type hints, dataclasses where they clarify data shape, and focused functions. Keep modules narrow: CLI wiring belongs in `cli.py`, Cloudflare HTTP behavior in `cloudflare.py`, and rule decisions in `sync.py`. Prefer explicit names such as `filter_managed_rules` or `build_launch_agent_plist`.

## Testing Guidelines

Tests use `pytest`. Add or update tests for every behavior change, especially sync safety, Keychain-independent setup behavior, and LaunchAgent output. Name test files `tests/test_<area>.py` and test functions `test_<expected_behavior>`. Use documentation IP ranges such as `192.0.2.0/24`, `198.51.100.0/24`, or `203.0.113.0/24`; do not commit real production IPs, tokens, or account IDs.

## Commit & Pull Request Guidelines

Recent history uses short imperative subjects, with occasional Conventional Commit prefixes, for example `Improve setup README` and `feat: Add interactive setup and LaunchAgent testing`. Keep commits focused and include tests/docs with the code change. PRs should summarize behavior changes, list verification commands, call out Cloudflare or macOS effects, and mention any migration or manual user action.

## Security & Configuration Tips

Never store Cloudflare tokens in files. The CLI stores tokens in macOS Keychain and non-secret config in `~/Library/Application Support/cf-ip-access-sync/config.json`. Use `--dry-run` and `test-agent` before enabling automation. Avoid exposing real account IDs, rule IDs, IPs, or token values in docs, tests, screenshots, or logs.
