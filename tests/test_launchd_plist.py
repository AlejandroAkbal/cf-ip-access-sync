from pathlib import Path

from cf_ip_access_sync.launchd import build_launch_agent_plist


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
