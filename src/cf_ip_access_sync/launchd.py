from __future__ import annotations

import os
from pathlib import Path
import plistlib
import subprocess
from typing import Any, Callable

from .config import APP_NAME, validate_profile


Runner = Callable[..., subprocess.CompletedProcess]


def agent_label(profile: str) -> str:
    validate_profile(profile)
    return f"com.{APP_NAME}.{profile}"


def launch_agents_dir(home: Path | None = None) -> Path:
    root = home if home is not None else Path.home()
    return root / "Library" / "LaunchAgents"


def logs_dir(home: Path | None = None) -> Path:
    root = home if home is not None else Path.home()
    return root / "Library" / "Logs" / APP_NAME


def plist_path(profile: str, home: Path | None = None) -> Path:
    return launch_agents_dir(home) / f"{agent_label(profile)}.plist"


def build_launch_agent_plist(profile: str, executable: Path, interval: int, home: Path | None = None) -> dict[str, Any]:
    validate_profile(profile)
    executable_path = Path(executable)
    if not executable_path.is_absolute():
        raise ValueError("LaunchAgent executable path must be absolute")
    if interval <= 0:
        raise ValueError("LaunchAgent interval must be positive")
    log_root = logs_dir(home)
    return {
        "Label": agent_label(profile),
        "ProgramArguments": [str(executable_path), "sync", "--profile", profile],
        "RunAtLoad": True,
        "StartInterval": int(interval),
        "StandardOutPath": str(log_root / f"{profile}.out.log"),
        "StandardErrorPath": str(log_root / f"{profile}.err.log"),
    }


def write_launch_agent_plist(profile: str, executable: Path, interval: int, home: Path | None = None) -> Path:
    launch_agents_dir(home).mkdir(parents=True, exist_ok=True)
    logs_dir(home).mkdir(parents=True, exist_ok=True)
    path = plist_path(profile, home)
    plist = build_launch_agent_plist(profile, executable, interval, home)
    with path.open("wb") as fh:
        plistlib.dump(plist, fh, sort_keys=True)
    return path


def install_launch_agent(
    profile: str,
    executable: Path,
    interval: int,
    home: Path | None = None,
    runner: Runner = subprocess.run,
) -> Path:
    path = write_launch_agent_plist(profile, executable, interval, home)
    label = agent_label(profile)
    domain = f"gui/{os.getuid()}"
    runner(["launchctl", "bootout", f"{domain}/{label}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    runner(["launchctl", "bootstrap", domain, str(path)], check=True)
    runner(["launchctl", "kickstart", "-k", f"{domain}/{label}"], check=True)
    return path


def uninstall_launch_agent(profile: str, home: Path | None = None, runner: Runner = subprocess.run) -> Path:
    path = plist_path(profile, home)
    label = agent_label(profile)
    domain = f"gui/{os.getuid()}"
    runner(["launchctl", "bootout", f"{domain}/{label}"], check=False)
    if path.exists():
        path.unlink()
    return path
