from __future__ import annotations

from dataclasses import dataclass
import getpass
import sys
from typing import Callable, TextIO

from .config import DEFAULT_INTERVAL_SECONDS, ProfileConfig, save_profile_config
from .keychain import store_token


DEFAULT_SETUP_PROFILE = "work"
DEFAULT_SETUP_INTERVAL_SECONDS = DEFAULT_INTERVAL_SECONDS
ACCOUNT_ID_DOCS_URL = "https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/"
CLOUDFLARE_DASHBOARD_URL = "https://dash.cloudflare.com"
TOKEN_DASHBOARD_URL = "https://dash.cloudflare.com/profile/api-tokens"


class SetupError(RuntimeError):
    """Raised for expected interactive setup failures."""


@dataclass(frozen=True, slots=True)
class SetupAnswers:
    profile: str
    account_id: str
    token: str
    ip_versions: list[str]
    interval_seconds: int


InputFunc = Callable[[str], str]
SecretFunc = Callable[[str], str]
ProfileFunc = Callable[[str], int]
InstallAgentFunc = Callable[[str, int], object]


def parse_yes_no(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"y", "yes"}:
        return True
    if normalized in {"n", "no"}:
        return False
    return None


def ensure_interactive(stdin: object = sys.stdin) -> None:
    isatty = getattr(stdin, "isatty", None)
    if not callable(isatty) or not isatty():
        raise SetupError(
            "setup requires an interactive terminal; use configure --token-stdin for non-interactive setup"
        )


def collect_setup_answers(
    *,
    profile: str | None,
    account_id: str | None,
    interval: int | None,
    ipv6: bool,
    no_agent: bool,
    input_func: InputFunc = input,
    secret_func: SecretFunc = getpass.getpass,
    output: TextIO = sys.stdout,
) -> SetupAnswers:
    selected_profile = _prompt_text(
        "Profile",
        default=profile or DEFAULT_SETUP_PROFILE,
        input_func=input_func,
        output=output,
    )

    print("", file=output)
    print("Find your Cloudflare Account ID:", file=output)
    print(f"1. Open {CLOUDFLARE_DASHBOARD_URL}", file=output)
    print("2. Select the Cloudflare account that owns the sites you want to allowlist.", file=output)
    print("3. Copy the Account ID from the account home or overview details.", file=output)
    print("Use the Account ID, not a Zone ID.", file=output)
    print(f"Cloudflare guide: {ACCOUNT_ID_DOCS_URL}", file=output)
    print("", file=output)

    selected_account_id = _prompt_text(
        "Cloudflare Account ID",
        default=account_id,
        input_func=input_func,
        output=output,
    )

    print("", file=output)
    print("Create a Cloudflare API token with these values:", file=output)
    print(f"Dashboard: {TOKEN_DASHBOARD_URL}", file=output)
    print(f"Token name: cf-ip-access-sync {selected_profile}", file=output)
    print("Permission: Account -> Account Firewall Access Rules -> Edit", file=output)
    print("Scope: the Cloudflare account you entered above", file=output)
    print("", file=output)

    token = _prompt_secret("Cloudflare API token", secret_func=secret_func, output=output)
    selected_ipv6 = True if ipv6 else _prompt_yes_no(
        "Enable IPv6 syncing",
        default=False,
        input_func=input_func,
        output=output,
    )
    selected_interval = _prompt_interval(
        "Sync interval seconds",
        default=interval or DEFAULT_SETUP_INTERVAL_SECONDS,
        input_func=input_func,
        output=output,
    )
    ip_versions = ["ipv4", "ipv6"] if selected_ipv6 else ["ipv4"]
    return SetupAnswers(
        profile=selected_profile,
        account_id=selected_account_id,
        token=token,
        ip_versions=ip_versions,
        interval_seconds=selected_interval,
    )


def build_profile_config(answers: SetupAnswers) -> ProfileConfig:
    return ProfileConfig(
        account_id=answers.account_id,
        profile=answers.profile,
        ip_versions=answers.ip_versions,
        interval_seconds=answers.interval_seconds,
    )


def run_setup(
    *,
    profile: str | None,
    account_id: str | None,
    interval: int | None,
    ipv6: bool,
    no_agent: bool,
    status_func: ProfileFunc,
    dry_run_func: ProfileFunc,
    install_agent_func: InstallAgentFunc,
    stdin: object = sys.stdin,
    input_func: InputFunc = input,
    secret_func: SecretFunc = getpass.getpass,
    output: TextIO = sys.stdout,
    save_config_func: Callable[[ProfileConfig], object] = save_profile_config,
    store_token_func: Callable[[str, str, str], None] = store_token,
) -> int:
    ensure_interactive(stdin)
    answers = collect_setup_answers(
        profile=profile,
        account_id=account_id,
        interval=interval,
        ipv6=ipv6,
        no_agent=no_agent,
        input_func=input_func,
        secret_func=secret_func,
        output=output,
    )
    config = build_profile_config(answers)

    store_token_func(config.account_id, config.profile, answers.token)
    config_path = save_config_func(config)
    print(f"Configured profile={config.profile} config={config_path} token_source=keychain", file=output)

    print("", file=output)
    print("Checking current status...", file=output)
    status_result = status_func(config.profile)
    if status_result != 0:
        print("status check failed; dry run and LaunchAgent install were skipped", file=output)
        return status_result

    print("", file=output)
    print("Previewing Cloudflare changes...", file=output)
    dry_run_result = dry_run_func(config.profile)
    if dry_run_result != 0:
        print("dry run failed; LaunchAgent was not installed", file=output)
        return dry_run_result

    install_agent = False if no_agent else _prompt_yes_no(
        "Install automatic background sync",
        default=True,
        input_func=input_func,
        output=output,
    )
    if install_agent:
        path = install_agent_func(config.profile, config.interval_seconds)
        print(f"installed profile={config.profile} plist={path} interval={config.interval_seconds}", file=output)
    else:
        print("LaunchAgent install skipped", file=output)
    return 0


def _prompt_text(
    label: str,
    *,
    default: str | None,
    input_func: InputFunc,
    output: TextIO,
) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input_func(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        print(f"{label} is required.", file=output)


def _prompt_secret(label: str, *, secret_func: SecretFunc, output: TextIO) -> str:
    while True:
        value = secret_func(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} is required.", file=output)


def _prompt_yes_no(
    label: str,
    *,
    default: bool,
    input_func: InputFunc,
    output: TextIO,
) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input_func(f"{label} [{suffix}]: ").strip()
        if not value:
            return default
        parsed = parse_yes_no(value)
        if parsed is not None:
            return parsed
        print("Please answer yes or no.", file=output)


def _prompt_interval(
    label: str,
    *,
    default: int,
    input_func: InputFunc,
    output: TextIO,
) -> int:
    while True:
        value = input_func(f"{label} [{default}]: ").strip()
        if not value:
            return default
        try:
            interval = int(value)
        except ValueError:
            print("Interval must be a positive number of seconds.", file=output)
            continue
        if interval > 0:
            return interval
        print("Interval must be a positive number of seconds.", file=output)
