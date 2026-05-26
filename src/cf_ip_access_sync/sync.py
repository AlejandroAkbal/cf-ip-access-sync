from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
from pathlib import Path
import socket
from typing import Iterable, Iterator

from .cloudflare import AccessRule
from .config import ProfileConfig, lock_path, managed_marker


MODE = "whitelist"


@dataclass(slots=True)
class SyncResult:
    family: str
    current_ip: str
    action: str
    rule_id: str | None = None
    detail: str = ""


def target_for_family(family: str) -> str:
    if family == "ipv4":
        return "ip"
    if family == "ipv6":
        return "ip6"
    raise ValueError(f"unsupported IP family: {family}")


def filter_managed_rules(rules: Iterable[AccessRule], profile: str, family: str) -> list[AccessRule]:
    marker = managed_marker(profile, family)
    return [rule for rule in rules if marker in (rule.notes or "")]


def build_rule_notes(profile: str, family: str, now: datetime | None = None, host: str | None = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    updated_at = timestamp.isoformat().replace("+00:00", "Z")
    hostname = (host or socket.getfqdn() or socket.gethostname()).replace(" ", "-")
    return f"{managed_marker(profile, family)} host={hostname} updated_at={updated_at}"


def sync_rules(config: ProfileConfig, client, current_ips: dict[str, str], dry_run: bool = False) -> list[SyncResult]:
    all_rules = client.list_access_rules(config.account_id, notes=config.managed_note_marker)
    results: list[SyncResult] = []
    for family in config.ip_versions:
        if family not in current_ips:
            continue
        current_ip = current_ips[family]
        target = target_for_family(family)
        managed_rules = filter_managed_rules(all_rules, config.profile, family)
        keeper = _choose_keeper(managed_rules, target, current_ip)
        notes = build_rule_notes(config.profile, family)

        if keeper is None:
            if dry_run:
                results.append(SyncResult(family=family, current_ip=current_ip, action="dry_run", detail="would_create"))
            else:
                created = client.create_access_rule(config.account_id, target, current_ip, MODE, notes)
                results.append(SyncResult(family=family, current_ip=current_ip, action="created", rule_id=created.id))
            continue

        if _rule_matches(keeper, target, current_ip):
            results.append(SyncResult(family=family, current_ip=current_ip, action="unchanged", rule_id=keeper.id))
        elif dry_run:
            results.append(
                SyncResult(
                    family=family,
                    current_ip=current_ip,
                    action="dry_run",
                    rule_id=keeper.id,
                    detail="would_update",
                )
            )
        else:
            updated = client.update_access_rule(config.account_id, keeper.id, target, current_ip, MODE, notes)
            results.append(SyncResult(family=family, current_ip=current_ip, action="updated", rule_id=updated.id))

        duplicate_rules = [rule for rule in managed_rules if rule.id != keeper.id]
        if config.cleanup_duplicates:
            for duplicate in duplicate_rules:
                if dry_run:
                    results.append(
                        SyncResult(
                            family=family,
                            current_ip=current_ip,
                            action="dry_run",
                            rule_id=duplicate.id,
                            detail="would_delete_duplicate",
                        )
                    )
                else:
                    deleted_id = client.delete_access_rule(config.account_id, duplicate.id)
                    results.append(
                        SyncResult(
                            family=family,
                            current_ip=current_ip,
                            action="duplicate_deleted",
                            rule_id=deleted_id,
                        )
                    )
    return results


def _rule_matches(rule: AccessRule, target: str, value: str) -> bool:
    return rule.mode == MODE and rule.target == target and rule.value == value


def _choose_keeper(rules: list[AccessRule], target: str, current_ip: str) -> AccessRule | None:
    if not rules:
        return None
    for rule in rules:
        if _rule_matches(rule, target, current_ip):
            return rule
    best = rules[0]
    best_key = _rule_timestamp(best)
    for rule in rules[1:]:
        key = _rule_timestamp(rule)
        if key > best_key:
            best = rule
            best_key = key
    return best


def _rule_timestamp(rule: AccessRule) -> str:
    return rule.modified_on or rule.created_on or ""


@contextmanager
def profile_lock(profile: str, home: Path | None = None) -> Iterator[None]:
    path = lock_path(profile, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
