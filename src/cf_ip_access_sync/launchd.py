from __future__ import annotations

import os
from pathlib import Path
import plistlib
import subprocess
from typing import Any, Callable

from .config import APP_NAME, validate_profile


Runner = Callable[..., subprocess.CompletedProcess]
LAUNCHD_DEFAULT_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


class LaunchAgentError(RuntimeError):
    """Raised when LaunchAgent configuration cannot be tested."""


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


def read_launch_agent_plist(profile: str, home: Path | None = None) -> dict[str, Any]:
    path = plist_path(profile, home)
    if not path.exists():
        raise LaunchAgentError(f"LaunchAgent plist not found: {path}")
    with path.open("rb") as fh:
        plist = plistlib.load(fh)
    if not isinstance(plist, dict):
        raise LaunchAgentError(f"LaunchAgent plist is invalid: {path}")
    return plist


def build_launch_agent_dry_run_command(plist: dict[str, Any]) -> list[str]:
    arguments = plist.get("ProgramArguments")
    if not isinstance(arguments, list) or not arguments:
        raise LaunchAgentError("LaunchAgent plist has no ProgramArguments")
    command = [str(arg) for arg in arguments]
    executable = Path(command[0])
    if not executable.is_absolute():
        raise LaunchAgentError("LaunchAgent ProgramArguments must start with an absolute executable path")
    if "sync" not in command:
        raise LaunchAgentError("LaunchAgent ProgramArguments do not run the sync command")
    if "--dry-run" not in command:
        command.append("--dry-run")
    return command


def launchd_like_environment(
    home: Path | None = None,
    source_env: dict[str, str] | None = None,
) -> dict[str, str]:
    source = source_env if source_env is not None else os.environ
    env = {
        "HOME": str(home or Path.home()),
        "PATH": LAUNCHD_DEFAULT_PATH,
    }
    for key in ("USER", "LOGNAME", "TMPDIR", "__CF_USER_TEXT_ENCODING"):
        value = source.get(key)
        if value:
            env[key] = value
    return env


def run_launch_agent_dry_run(
    profile: str,
    home: Path | None = None,
    runner: Runner = subprocess.run,
    source_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    plist = read_launch_agent_plist(profile, home)
    command = build_launch_agent_dry_run_command(plist)
    return runner(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=launchd_like_environment(home, source_env),
    )


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
