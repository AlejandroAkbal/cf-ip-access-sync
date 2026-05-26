from __future__ import annotations

import argparse

from cf_ip_access_sync import cli
from cf_ip_access_sync.cloudflare import AccessRule
from cf_ip_access_sync.config import ProfileConfig


EXAMPLE_CURRENT_IP = "203.0.113.10"


class FakeCloudflareClient:
    def __init__(self, _token):
        pass

    def list_access_rules(self, account_id, notes=None, page=1, per_page=50):
        return [
            AccessRule(
                id="manual-current",
                mode="whitelist",
                configuration={"target": "ip", "value": EXAMPLE_CURRENT_IP},
                notes="Me",
            )
        ]


def test_status_reports_unmanaged_allow_rule_for_current_ip(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "load_profile_config",
        lambda profile: ProfileConfig(account_id="abc123def456", profile=profile),
    )
    monkeypatch.setattr(cli, "resolve_token", lambda account_id, profile: ("secret-token", "keychain"))
    monkeypatch.setattr(
        cli,
        "detect_public_ip",
        lambda family: EXAMPLE_CURRENT_IP if family == "ipv4" else (_raise_ipv6_unavailable()),
    )
    monkeypatch.setattr(cli, "CloudflareClient", FakeCloudflareClient)

    result = cli._status(argparse.Namespace(profile="laptop"))

    assert result == 0
    output = capsys.readouterr().out
    assert "managed_ipv4: none" in output
    assert f"unmanaged_ipv4_allow_for_current_ip: id=manual-current value={EXAMPLE_CURRENT_IP} notes=Me" in output


def _raise_ipv6_unavailable():
    from cf_ip_access_sync.ip_detect import IPDetectionError

    raise IPDetectionError("no ipv6")
