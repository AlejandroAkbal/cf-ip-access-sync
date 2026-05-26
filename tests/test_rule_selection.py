from cf_ip_access_sync.cloudflare import AccessRule
from cf_ip_access_sync.config import ProfileConfig
from cf_ip_access_sync.sync import filter_managed_rules, sync_rules


class FakeCloudflareClient:
    def __init__(self, rules):
        self.rules = list(rules)
        self.created = []
        self.updated = []
        self.deleted = []

    def list_access_rules(self, account_id, notes=None, page=1, per_page=50):
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


def test_duplicate_cleanup_deletes_only_exact_marker_duplicates():
    managed_current = rule("keep", "cf-ip-access-sync profile=work managed=true family=ipv4", value="8.8.8.8")
    managed_old = rule("delete", "cf-ip-access-sync profile=work managed=true family=ipv4", value="1.1.1.1")
    similar_manual = rule("manual", "cf-ip-access-sync profile=work managed=false family=ipv4", value="1.1.1.1")
    client = FakeCloudflareClient([managed_old, similar_manual, managed_current])

    results = sync_rules(config(), client, {"ipv4": "8.8.8.8"})

    assert client.updated == []
    assert client.created == []
    assert client.deleted == [("abc123def456", "delete")]
    assert [result.action for result in results] == ["unchanged", "duplicate_deleted"]


def test_existing_managed_rule_is_patched_when_ip_changes():
    managed_old = rule("managed", "cf-ip-access-sync profile=work managed=true family=ipv4", value="1.1.1.1")
    client = FakeCloudflareClient([managed_old])

    results = sync_rules(config(), client, {"ipv4": "8.8.8.8"})

    assert client.updated[0][1:5] == ("managed", "ip", "8.8.8.8", "whitelist")
    assert client.created == []
    assert client.deleted == []
    assert results[0].action == "updated"


def test_dry_run_makes_no_create_update_or_delete_calls():
    managed_old = rule("managed", "cf-ip-access-sync profile=work managed=true family=ipv4", value="1.1.1.1")
    duplicate = rule("duplicate", "cf-ip-access-sync profile=work managed=true family=ipv4", value="2.2.2.2")
    client = FakeCloudflareClient([managed_old, duplicate])

    results = sync_rules(config(), client, {"ipv4": "8.8.8.8"}, dry_run=True)

    assert client.created == []
    assert client.updated == []
    assert client.deleted == []
    assert [result.action for result in results] == ["dry_run", "dry_run"]
