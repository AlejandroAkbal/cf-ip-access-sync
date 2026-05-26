from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .cloudflare import CloudflareAPIError, CloudflareClient
from .config import (
    ConfigError,
    DEFAULT_INTERVAL_SECONDS,
    ProfileConfig,
    config_path,
    load_profile_config,
    mask_account_id,
    save_profile_config,
)
from .ip_detect import IPDetectionError, detect_public_ip
from .keychain import KeychainError, resolve_token, store_token
from .launchd import LaunchAgentError, install_launch_agent, plist_path, run_launch_agent_dry_run, uninstall_launch_agent
from .logging_utils import configure_logging
from .setup import SetupError, run_setup
from .sync import SyncResult, filter_matching_rules, filter_managed_rules, profile_lock, sync_rules


class CLIError(RuntimeError):
    """Raised for expected command-line failures."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cf-ip-access-sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup", help="Interactively configure this tool for first use")
    setup.add_argument("--profile", help="Profile name to prefill")
    setup.add_argument("--account-id", help="Cloudflare Account ID to prefill")
    setup.add_argument("--interval", type=int, help="Sync interval in seconds to prefill")
    setup.add_argument("--ipv6", action="store_true", help="Preselect IPv6 syncing")
    setup.add_argument("--no-agent", action="store_true", help="Do not install the LaunchAgent")

    configure = subparsers.add_parser("configure", help="Save profile config and optionally store the token in Keychain")
    configure.add_argument("--account-id", required=True)
    configure.add_argument("--profile", default="default")
    configure.add_argument("--token-stdin", action="store_true")
    configure.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS)
    configure.add_argument("--log-level", default="INFO")
    configure.add_argument("--ipv6", action="store_true", help="Enable IPv6 syncing in the saved profile")

    sync = subparsers.add_parser("sync", help="Perform one idempotent sync")
    sync.add_argument("--profile", default="default")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--ipv6", action="store_true", help="Also sync IPv6 for this run")

    status = subparsers.add_parser("status", help="Show local and Cloudflare managed-rule state")
    status.add_argument("--profile", default="default")

    install = subparsers.add_parser("install-agent", help="Install a per-user LaunchAgent")
    install.add_argument("--profile", default="default")
    install.add_argument("--interval", type=int)

    test_agent = subparsers.add_parser("test-agent", help="Run the installed LaunchAgent command with --dry-run")
    test_agent.add_argument("--profile", default="default")

    uninstall = subparsers.add_parser("uninstall-agent", help="Unload and remove the LaunchAgent")
    uninstall.add_argument("--profile", default="default")

    remove = subparsers.add_parser("remove-managed-rule", help="Delete only this profile's managed Cloudflare rules")
    remove.add_argument("--profile", default="default")
    remove.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            return _setup(args)
        if args.command == "configure":
            return _configure(args)
        if args.command == "sync":
            return _sync(args)
        if args.command == "status":
            return _status(args)
        if args.command == "install-agent":
            return _install_agent(args)
        if args.command == "test-agent":
            return _test_agent(args)
        if args.command == "uninstall-agent":
            return _uninstall_agent(args)
        if args.command == "remove-managed-rule":
            return _remove_managed_rule(args)
    except (CLIError, ConfigError, CloudflareAPIError, IPDetectionError, KeychainError, OSError, SetupError, LaunchAgentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 2


def _setup(args: argparse.Namespace) -> int:
    return run_setup(
        profile=args.profile,
        account_id=args.account_id,
        interval=args.interval,
        ipv6=args.ipv6,
        no_agent=args.no_agent,
        status_func=_status_for_profile,
        dry_run_func=_dry_run_for_profile,
        install_agent_func=_install_agent_for_profile,
    )


def _configure(args: argparse.Namespace) -> int:
    families = ["ipv4"]
    if args.ipv6:
        families.append("ipv6")
    config = ProfileConfig(
        account_id=args.account_id,
        profile=args.profile,
        ip_versions=families,
        interval_seconds=args.interval,
        log_level=args.log_level,
    )
    path = save_profile_config(config)
    if args.token_stdin:
        token = sys.stdin.read().strip()
        if not token:
            raise CLIError("--token-stdin was provided but stdin was empty")
        store_token(config.account_id, config.profile, token)
        token_text = "token_source=keychain"
    else:
        token_text = "token_source=unchanged"
    print(f"configured profile={config.profile} config={path} {token_text}")
    return 0


def _sync(args: argparse.Namespace) -> int:
    config = load_profile_config(args.profile)
    configure_logging(config.log_level)
    if args.ipv6 and "ipv6" not in config.ip_versions:
        config.ip_versions.append("ipv6")
    with profile_lock(config.profile):
        token, source = resolve_token(config.account_id, config.profile)
        if not token:
            raise CLIError("Cloudflare token missing; run configure --token-stdin or set CLOUDFLARE_API_TOKEN")
        current_ips = _detect_current_ips(config.ip_versions)
        client = CloudflareClient(token)
        results = sync_rules(config, client, current_ips, dry_run=args.dry_run)
    for result in results:
        print(_format_result(result, token_source=source if args.dry_run else None))
    return 0


def _status(args: argparse.Namespace) -> int:
    config = load_profile_config(args.profile)
    token, source = resolve_token(config.account_id, config.profile)
    print(f"config_path: {config_path()}")
    print(f"account_id: {mask_account_id(config.account_id)}")
    print(f"token_source: {source}")
    detected: dict[str, str] = {}
    for family in ("ipv4", "ipv6"):
        try:
            detected[family] = detect_public_ip(family)
            print(f"current_{family}: {detected[family]}")
        except IPDetectionError as exc:
            print(f"current_{family}: unavailable ({exc})")
    if not token:
        print("managed_rules: skipped (token missing)")
        return 0
    client = CloudflareClient(token)
    rules = client.list_access_rules(config.account_id)
    for family in ("ipv4", "ipv6"):
        managed = filter_managed_rules(rules, config.profile, family)
        managed_rule_ids = {rule.id for rule in managed}
        target = "ip6" if family == "ipv6" else "ip"
        if not managed:
            print(f"managed_{family}: none")
        else:
            for rule in managed:
                matches = rule.mode == "whitelist" and rule.target == target and rule.value == detected.get(family)
                print(f"managed_{family}: id={rule.id} value={rule.value} matches_current={str(matches).lower()}")
        for rule in filter_matching_rules(rules, target, detected.get(family, "")):
            if rule.id not in managed_rule_ids:
                note = f" notes={_format_detail_value(rule.notes)}" if rule.notes else ""
                print(f"unmanaged_{family}_allow_for_current_ip: id={rule.id} value={rule.value}{note}")
    return 0


def _install_agent(args: argparse.Namespace) -> int:
    config = load_profile_config(args.profile)
    interval = args.interval or config.interval_seconds
    if args.interval:
        config.interval_seconds = args.interval
        save_profile_config(config)
    executable = _console_script_path()
    path = install_launch_agent(config.profile, executable, interval)
    print(f"installed profile={config.profile} plist={path} interval={interval}")
    return 0


def _test_agent(args: argparse.Namespace) -> int:
    path = plist_path(args.profile)
    print(f"plist: {path}")
    result = run_launch_agent_dry_run(args.profile)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    print(f"exit_code: {result.returncode}")
    return int(result.returncode)


def _status_for_profile(profile: str) -> int:
    return _status(argparse.Namespace(profile=profile))


def _dry_run_for_profile(profile: str) -> int:
    return _sync(argparse.Namespace(profile=profile, dry_run=True, ipv6=False))


def _install_agent_for_profile(profile: str, interval: int) -> Path:
    config = load_profile_config(profile)
    config.interval_seconds = interval
    save_profile_config(config)
    executable = _console_script_path()
    return install_launch_agent(config.profile, executable, interval)


def _uninstall_agent(args: argparse.Namespace) -> int:
    path = uninstall_launch_agent(args.profile)
    print(f"uninstalled profile={args.profile} plist={path}")
    return 0


def _remove_managed_rule(args: argparse.Namespace) -> int:
    if not args.confirm:
        raise CLIError("remove-managed-rule requires --confirm")
    config = load_profile_config(args.profile)
    token, _source = resolve_token(config.account_id, config.profile)
    if not token:
        raise CLIError("Cloudflare token missing; run configure --token-stdin or set CLOUDFLARE_API_TOKEN")
    client = CloudflareClient(token)
    rules = client.list_access_rules(config.account_id, notes=config.managed_note_marker)
    to_delete = []
    for family in ("ipv4", "ipv6"):
        to_delete.extend(filter_managed_rules(rules, config.profile, family))
    seen = set()
    deleted = []
    for rule in to_delete:
        if rule.id in seen:
            continue
        seen.add(rule.id)
        deleted.append(client.delete_access_rule(config.account_id, rule.id))
    if not deleted:
        print(f"removed profile={config.profile} count=0")
    for rule_id in deleted:
        print(f"removed profile={config.profile} rule_id={rule_id}")
    return 0


def _detect_current_ips(families: list[str]) -> dict[str, str]:
    current_ips = {}
    for family in families:
        current_ips[family] = detect_public_ip(family)
    return current_ips


def _format_result(result: SyncResult, token_source: str | None = None) -> str:
    parts = [
        f"family={result.family}",
        f"current_ip={result.current_ip}",
        f"action={result.action}",
    ]
    if result.rule_id:
        parts.append(f"rule_id={result.rule_id}")
    if result.detail:
        parts.append(f"detail={result.detail}")
    if token_source:
        parts.append(f"token_source={token_source}")
    return " ".join(parts)


def _format_detail_value(value: str) -> str:
    return "_".join(value.split())


def _console_script_path() -> Path:
    path = shutil.which("cf-ip-access-sync")
    if path:
        return Path(path).resolve()
    candidate = Path(sys.argv[0])
    if candidate.is_absolute() and candidate.name == "cf-ip-access-sync":
        return candidate.resolve()
    raise CLIError("could not find absolute cf-ip-access-sync executable; install with pip first")
