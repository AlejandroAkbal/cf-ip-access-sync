from cf_ip_access_sync.cloudflare import build_access_rule_payload
from cf_ip_access_sync.sync import target_for_family


def test_ipv4_payload_uses_ip_target_and_whitelist_mode():
    payload = build_access_rule_payload("ip", "8.8.8.8", "whitelist", "note")

    assert payload == {
        "mode": "whitelist",
        "configuration": {"target": "ip", "value": "8.8.8.8"},
        "notes": "note",
    }


def test_ipv6_payload_uses_ip6_target_and_whitelist_mode():
    payload = build_access_rule_payload(target_for_family("ipv6"), "2001:4860:4860::8888", "whitelist", "note")

    assert payload["mode"] == "whitelist"
    assert payload["configuration"] == {"target": "ip6", "value": "2001:4860:4860::8888"}
