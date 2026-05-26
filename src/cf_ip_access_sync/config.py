from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any


APP_NAME = "cf-ip-access-sync"
DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_LOG_LEVEL = "INFO"
VALID_FAMILIES = {"ipv4", "ipv6"}
PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class ConfigError(RuntimeError):
    """Raised when local configuration is missing or invalid."""


@dataclass(slots=True)
class ProfileConfig:
    account_id: str
    profile: str = "default"
    managed_note_marker: str | None = None
    ip_versions: list[str] = field(default_factory=lambda: ["ipv4"])
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    log_level: str = DEFAULT_LOG_LEVEL
    cleanup_duplicates: bool = True

    def __post_init__(self) -> None:
        validate_profile(self.profile)
        if not self.account_id:
            raise ConfigError("account_id is required")
        if self.managed_note_marker is None:
            self.managed_note_marker = base_managed_marker(self.profile)
        normalized = []
        for family in self.ip_versions:
            if family not in VALID_FAMILIES:
                raise ConfigError(f"unsupported IP family: {family}")
            if family not in normalized:
                normalized.append(family)
        if not normalized:
            raise ConfigError("at least one IP family must be configured")
        self.ip_versions = normalized
        if self.interval_seconds <= 0:
            raise ConfigError("interval_seconds must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "profile": self.profile,
            "managed_note_marker": self.managed_note_marker,
            "ip_versions": list(self.ip_versions),
            "interval_seconds": self.interval_seconds,
            "log_level": self.log_level,
            "cleanup_duplicates": self.cleanup_duplicates,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], profile: str | None = None) -> "ProfileConfig":
        merged = dict(data)
        if profile is not None:
            merged["profile"] = profile
        return cls(
            account_id=str(merged.get("account_id", "")),
            profile=str(merged.get("profile", "default")),
            managed_note_marker=merged.get("managed_note_marker"),
            ip_versions=list(merged.get("ip_versions", ["ipv4"])),
            interval_seconds=int(merged.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)),
            log_level=str(merged.get("log_level", DEFAULT_LOG_LEVEL)),
            cleanup_duplicates=bool(merged.get("cleanup_duplicates", True)),
        )


def validate_profile(profile: str) -> None:
    if not profile or not PROFILE_RE.fullmatch(profile):
        raise ConfigError("profile must contain only letters, numbers, dot, underscore, or dash")


def base_managed_marker(profile: str) -> str:
    validate_profile(profile)
    return f"{APP_NAME} profile={profile} managed=true"


def managed_marker(profile: str, family: str) -> str:
    if family not in VALID_FAMILIES:
        raise ConfigError(f"unsupported IP family: {family}")
    return f"{base_managed_marker(profile)} family={family}"


def app_support_dir(home: Path | None = None) -> Path:
    root = home if home is not None else Path.home()
    return root / "Library" / "Application Support" / APP_NAME


def config_path(home: Path | None = None) -> Path:
    return app_support_dir(home) / "config.json"


def lock_path(profile: str, home: Path | None = None) -> Path:
    validate_profile(profile)
    return app_support_dir(home) / f"{profile}.lock"


def load_config_file(path: Path | None = None) -> dict[str, Any]:
    selected = path or config_path()
    if not selected.exists():
        raise ConfigError(f"config file not found: {selected}")
    with selected.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_profile_config(profile: str = "default", path: Path | None = None) -> ProfileConfig:
    validate_profile(profile)
    data = load_config_file(path)
    if "profiles" in data:
        profiles = data.get("profiles") or {}
        if profile not in profiles:
            raise ConfigError(f"profile not configured: {profile}")
        return ProfileConfig.from_dict(profiles[profile], profile=profile)
    if data.get("profile", "default") != profile:
        raise ConfigError(f"profile not configured: {profile}")
    return ProfileConfig.from_dict(data, profile=profile)


def save_profile_config(config: ProfileConfig, path: Path | None = None) -> Path:
    selected = path or config_path()
    selected.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any]
    if selected.exists():
        try:
            data = load_config_file(selected)
        except (ConfigError, json.JSONDecodeError):
            data = {}
    else:
        data = {}
    profiles = dict(data.get("profiles") or {})
    profiles[config.profile] = config.to_dict()
    data = {"profiles": profiles}
    tmp_path = selected.with_suffix(selected.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.chmod(tmp_path, 0o600)
    tmp_path.replace(selected)
    os.chmod(selected, 0o600)
    return selected


def mask_account_id(account_id: str) -> str:
    if len(account_id) <= 10:
        return "*" * len(account_id)
    return f"{account_id[:6]}...{account_id[-4:]}"
