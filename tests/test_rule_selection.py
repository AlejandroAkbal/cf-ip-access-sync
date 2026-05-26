from datetime import datetime, timezone

from cf_ip_access_sync.cloudflare import AccessRule
from cf_ip_access_sync.config import ProfileConfig
from cf_ip_access_sync.sync import build_rule_notes, filter_matching_rules, filter_managed_rules, sync_rules


class FakeCloudflareClient:
    def __init__(self, rules):
        self.rules = list(rules)
        self.created = []
        self.updated = []
        self.deleted = []

    def list_access_rules(self, account_id, notes=None, page=1, per_page=50):
        if notes:
            return [rule for rule in self.rules if notes in (rule.notes or "")]
        return list(self.rules)

    def create_access_rule(self, account_id, target, value, mode, notes):
        self.created.append((account_id, target, value, mode, notes))
        rule = AccessRule(id="created-rule", mode=mode, configuration={"target": target, "value": value}, notes=notes)
        self.rules.append(rule)
        return rule

    def update_access_rule(self, account_id, rule_id, target, value, mode, notes):
        self.updated.append((account_id, rule_id, target, value, mode, notes))
        return AccessRule(id=rule_id, mode=mode, configuration={"target": target, "value": value}, notes=notes)

    def delete_access_rule(self, account_id, rule_id):
        self.deleted.append((account_id, rule_id))
        return rule_id


def rule(rule_id, notes, value="1.1.1.1", target="ip", mode="whitelist", created_on="2026-05-26T00:00:00Z"):
    return AccessRule(
        id=rule_id,
        mode=mode,
        configuration={"target": target, "value": value},
        notes=notes,
        created_on=created_on,
    )


def config(cleanup_duplicates=True):
    return ProfileConfig(
        account_id="abc123def456",
        profile="work",
        managed_note_marker="cf-ip-access-sync profile=work managed=true",
        ip_versions=["ipv4"],
        cleanup_duplicates=cleanup_duplicates,
    )


def test_rule_selector_ignores_non_managed_rules():
    managed = rule("managed", "cf-ip-access-sync profile=work managed=true family=ipv4")
    unmanaged = rule("manual", "cf-ip-access-sync managed by a human")

    assert filter_managed_rules([managed, unmanaged], "work", "ipv4") == [managed]


EXAMPLE_CURRENT_IP = "203.0.113.10"
EXAMPLE_OTHER_IP = "198.51.100.20"
EXAMPLE_OLD_IP = "192.0.2.30"
EXAMPLE_DUPLICATE_IP = "192.0.2.31"


def test_matching_rule_selector_finds_existing_allow_rule_for_current_ip():
    current = rule("manual-current", "Me", value=EXAMPLE_CURRENT_IP)
    other = rule("manual-other", "Hosting EU", value=EXAMPLE_OTHER_IP)

    assert filter_matching_rules([other, current], "ip", EXAMPLE_CURRENT_IP) == [current]


def test_sync_does_not_create_duplicate_when_unmanaged_allow_rule_already_covers_current_ip():
    existing = rule("manual-current", "Me", value=EXAMPLE_CURRENT_IP)
    client = FakeCloudflareClient([existing])

    results = sync_rules(config(), client, {"ipv4": EXAMPLE_CURRENT_IP})

    assert client.created == []
    assert client.updated == []
    assert client.deleted == []
    assert len(results) == 1
    assert results[0].action == "covered_by_existing"
    assert results[0].rule_id == "manual-current"
    assert results[0].detail == "existing_unmanaged_allow_rule"


def test_rule_notes_prefer_local_hostname_over_reverse_dns(monkeypatch):
    monkeypatch.setattr("cf_ip_access_sync.sync.socket.gethostname", lambda: "example-mac.local")
    monkeypatch.setattr(
        "cf_ip_access_sync.sync.socket.getfqdn",
        lambda: "0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa",
    )

    notes = build_rule_notes(
        "laptop",
        "ipv4",
        now=datetime(2026, 5, 26, 20, 53, 4, tzinfo=timezone.utc),
    )

    assert notes == (
        "cf-ip-access-sync profile=laptop managed=true family=ipv4 "
        "host=example-mac.local updated_at=2026-05-26T20:53:04Z"
    )


def test_rule_notes_fall_back_to_unknown_for_reverse_dns_host():
    notes = build_rule_notes(
        "laptop",
        "ipv4",
        now=datetime(2026, 5, 26, 20, 53, 4, tzinfo=timezone.utc),
        host="0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa",
    )

    assert "host=unknown" in notes
    assert "ip6.arpa" not in notes


def test_sync_repairs_malformed_managed_note_host_when_ip_is_unchanged(monkeypatch):
    monkeypatch.setattr("cf_ip_access_sync.sync.socket.gethostname", lambda: "example-mac.local")
    monkeypatch.setattr("cf_ip_access_sync.sync.socket.getfqdn", lambda: "example-mac.local")
    managed_bad_note = rule(
        "managed",
        (
            "cf-ip-access-sync profile=work managed=true family=ipv4 "
            "host=0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa updated_at=2026-05-26T20:53:04Z"
        ),
        value=EXAMPLE_CURRENT_IP,
    )
    client = FakeCloudflareClient([managed_bad_note])

    results = sync_rules(config(), client, {"ipv4": EXAMPLE_CURRENT_IP})

    assert client.created == []
    assert client.updated[0][1:5] == ("managed", "ip", EXAMPLE_CURRENT_IP, "whitelist")
    assert "host=example-mac.local" in client.updated[0][5]
    assert "ip6.arpa" not in client.updated[0][5]
    assert results[0].action == "notes_updated"


def test_duplicate_cleanup_deletes_only_exact_marker_duplicates():
    managed_current = rule("keep", "cf-ip-access-sync profile=work managed=true family=ipv4", value=EXAMPLE_CURRENT_IP)
    managed_old = rule("delete", "cf-ip-access-sync profile=work managed=true family=ipv4", value=EXAMPLE_OLD_IP)
    similar_manual = rule("manual", "cf-ip-access-sync profile=work managed=false family=ipv4", value=EXAMPLE_OLD_IP)
    client = FakeCloudflareClient([managed_old, similar_manual, managed_current])

    results = sync_rules(config(), client, {"ipv4": EXAMPLE_CURRENT_IP})

    assert client.updated == []
    assert client.created == []
    assert client.deleted == [("abc123def456", "delete")]
    assert [result.action for result in results] == ["unchanged", "duplicate_deleted"]


def test_existing_managed_rule_is_patched_when_ip_changes():
    managed_old = rule("managed", "cf-ip-access-sync profile=work managed=true family=ipv4", value=EXAMPLE_OLD_IP)
    client = FakeCloudflareClient([managed_old])

    results = sync_rules(config(), client, {"ipv4": EXAMPLE_CURRENT_IP})

    assert client.updated[0][1:5] == ("managed", "ip", EXAMPLE_CURRENT_IP, "whitelist")
    assert client.created == []
    assert client.deleted == []
    assert results[0].action == "updated"


def test_dry_run_makes_no_create_update_or_delete_calls():
    managed_old = rule("managed", "cf-ip-access-sync profile=work managed=true family=ipv4", value=EXAMPLE_OLD_IP)
    duplicate = rule("duplicate", "cf-ip-access-sync profile=work managed=true family=ipv4", value=EXAMPLE_DUPLICATE_IP)
    client = FakeCloudflareClient([managed_old, duplicate])

    results = sync_rules(config(), client, {"ipv4": EXAMPLE_CURRENT_IP}, dry_run=True)

    assert client.created == []
    assert client.updated == []
    assert client.deleted == []
    assert [result.action for result in results] == ["dry_run", "dry_run"]
