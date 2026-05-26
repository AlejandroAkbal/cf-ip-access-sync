from pathlib import Path
import subprocess

from cf_ip_access_sync.launchd import (
    build_launch_agent_dry_run_command,
    build_launch_agent_plist,
    launchd_like_environment,
    run_launch_agent_dry_run,
    write_launch_agent_plist,
)


def test_launch_agent_plist_uses_absolute_executable_path_and_correct_label(tmp_path):
    executable = tmp_path / "bin" / "cf-ip-access-sync"
    executable.parent.mkdir()
    executable.touch()

    plist = build_launch_agent_plist("work", executable, 300, home=tmp_path)

    assert plist["Label"] == "com.cf-ip-access-sync.work"
    assert plist["ProgramArguments"] == [str(executable), "sync", "--profile", "work"]
    assert Path(plist["ProgramArguments"][0]).is_absolute()
    assert plist["RunAtLoad"] is True
    assert plist["StartInterval"] == 300
    assert plist["StandardOutPath"] == str(tmp_path / "Library" / "Logs" / "cf-ip-access-sync" / "work.out.log")
    assert plist["StandardErrorPath"] == str(tmp_path / "Library" / "Logs" / "cf-ip-access-sync" / "work.err.log")


def test_launch_agent_dry_run_command_uses_installed_program_arguments(tmp_path):
    executable = tmp_path / "bin" / "cf-ip-access-sync"
    executable.parent.mkdir()
    executable.touch()
    plist = build_launch_agent_plist("work", executable, 900, home=tmp_path)

    command = build_launch_agent_dry_run_command(plist)

    assert command == [str(executable), "sync", "--profile", "work", "--dry-run"]


def test_launchd_like_environment_is_sparse_and_does_not_inherit_token(tmp_path):
    env = launchd_like_environment(
        home=tmp_path,
        source_env={
            "USER": "alejandro",
            "LOGNAME": "alejandro",
            "CLOUDFLARE_API_TOKEN": "secret-token",
            "PATH": "/custom/bin",
        },
    )

    assert env == {
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "USER": "alejandro",
        "LOGNAME": "alejandro",
    }


def test_run_launch_agent_dry_run_executes_plist_command_with_sparse_environment(tmp_path):
    executable = tmp_path / "bin" / "cf-ip-access-sync"
    executable.parent.mkdir()
    executable.touch()
    write_launch_agent_plist("work", executable, 900, home=tmp_path)
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="dry-run ok\n", stderr="")

    result = run_launch_agent_dry_run(
        "work",
        home=tmp_path,
        runner=runner,
        source_env={"USER": "alejandro", "LOGNAME": "alejandro", "CLOUDFLARE_API_TOKEN": "secret-token"},
    )

    assert result.returncode == 0
    assert calls[0][0] == [str(executable), "sync", "--profile", "work", "--dry-run"]
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["text"] is True
    assert "CLOUDFLARE_API_TOKEN" not in calls[0][1]["env"]
