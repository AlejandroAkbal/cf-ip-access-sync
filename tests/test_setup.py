from __future__ import annotations

import io

import pytest

from cf_ip_access_sync.cli import build_parser
from cf_ip_access_sync.config import DEFAULT_INTERVAL_SECONDS
from cf_ip_access_sync.setup import (
    DEFAULT_SETUP_INTERVAL_SECONDS,
    DEFAULT_SETUP_PROFILE,
    SetupAnswers,
    SetupError,
    build_profile_config,
    collect_setup_answers,
    ensure_interactive,
    parse_yes_no,
    run_setup,
)


class NonTTY:
    def isatty(self):
        return False


def input_from(values):
    iterator = iter(values)

    def _input(_prompt):
        return next(iterator)

    return _input


def test_collect_setup_answers_uses_safe_defaults_and_prints_token_guidance():
    output = io.StringIO()

    answers = collect_setup_answers(
        profile=None,
        account_id=None,
        interval=None,
        ipv6=False,
        no_agent=False,
        input_func=input_from(["", "abc123def456", "", "", ""]),
        secret_func=lambda _prompt: "secret-token",
        output=output,
    )

    assert answers == SetupAnswers(
        profile=DEFAULT_SETUP_PROFILE,
        account_id="abc123def456",
        token="secret-token",
        ip_versions=["ipv4"],
        interval_seconds=DEFAULT_SETUP_INTERVAL_SECONDS,
        install_agent=True,
    )
    assert "cf-ip-access-sync work" in output.getvalue()
    assert "Open https://dash.cloudflare.com" in output.getvalue()
    assert "Copy the Account ID" in output.getvalue()
    assert "https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/" in output.getvalue()
    assert "https://dash.cloudflare.com/profile/api-tokens" in output.getvalue()
    assert "Account -> Account Firewall Access Rules -> Edit" in output.getvalue()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("y", True),
        ("yes", True),
        ("Y", True),
        ("n", False),
        ("no", False),
        ("NO", False),
        ("maybe", None),
        ("", None),
    ],
)
def test_parse_yes_no_accepts_common_short_forms(value, expected):
    assert parse_yes_no(value) is expected


def test_ensure_interactive_rejects_non_tty_stdin():
    with pytest.raises(SetupError, match="interactive terminal"):
        ensure_interactive(NonTTY())


def test_build_profile_config_preserves_ipv6_and_setup_interval():
    config = build_profile_config(
        SetupAnswers(
            profile="home",
            account_id="abc123def456",
            token="secret-token",
            ip_versions=["ipv4", "ipv6"],
            interval_seconds=900,
            install_agent=False,
        )
    )

    assert config.profile == "home"
    assert config.account_id == "abc123def456"
    assert config.ip_versions == ["ipv4", "ipv6"]
    assert config.interval_seconds == 900


def test_run_setup_skips_agent_install_when_dry_run_fails():
    calls = []
    output = io.StringIO()

    def save_config(config):
        calls.append(("save_config", config.profile, config.interval_seconds, tuple(config.ip_versions)))
        return "/tmp/config.json"

    def store_token(account_id, profile, token):
        calls.append(("store_token", account_id, profile, token))

    def status(profile):
        calls.append(("status", profile))
        return 0

    def dry_run(profile):
        calls.append(("dry_run", profile))
        return 1

    def install_agent(profile, interval):
        calls.append(("install_agent", profile, interval))
        return "/tmp/agent.plist"

    result = run_setup(
        profile=None,
        account_id=None,
        interval=None,
        ipv6=False,
        no_agent=False,
        stdin=type("TTY", (), {"isatty": lambda self: True})(),
        input_func=input_from(["", "abc123def456", "", "", ""]),
        secret_func=lambda _prompt: "secret-token",
        output=output,
        save_config_func=save_config,
        store_token_func=store_token,
        status_func=status,
        dry_run_func=dry_run,
        install_agent_func=install_agent,
    )

    assert result == 1
    assert ("install_agent", "work", 900) not in calls
    assert calls == [
        ("store_token", "abc123def456", "work", "secret-token"),
        ("save_config", "work", 900, ("ipv4",)),
        ("status", "work"),
        ("dry_run", "work"),
    ]
    assert "dry run failed" in output.getvalue()


def test_setup_parser_accepts_prefill_options():
    args = build_parser().parse_args(["setup", "--profile", "home", "--interval", "900", "--ipv6", "--no-agent"])

    assert args.command == "setup"
    assert args.profile == "home"
    assert args.interval == 900
    assert args.ipv6 is True
    assert args.no_agent is True


def test_test_agent_parser_accepts_profile():
    args = build_parser().parse_args(["test-agent", "--profile", "home"])

    assert args.command == "test-agent"
    assert args.profile == "home"


def test_project_default_interval_is_fifteen_minutes():
    assert DEFAULT_INTERVAL_SECONDS == 900


def test_configure_parser_default_interval_is_fifteen_minutes():
    args = build_parser().parse_args(["configure", "--account-id", "abc123def456"])

    assert args.interval == 900
