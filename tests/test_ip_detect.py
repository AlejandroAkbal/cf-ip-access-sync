import pytest

from cf_ip_access_sync.ip_detect import IPDetectionError, detect_public_ip, validate_public_ip


class FakeResponse:
    def __init__(self, body: str):
        self.body = body.encode("ascii")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit: int = -1):
        return self.body


def test_ip_validation_rejects_private_reserved_and_invalid_ips():
    for value in ["10.0.0.1", "127.0.0.1", "169.254.0.1", "198.51.100.4", "::1", "not-an-ip"]:
        with pytest.raises(IPDetectionError):
            validate_public_ip(value, version=None)


def test_ipv4_resolver_accepts_only_ipv4_and_fails_over():
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            return FakeResponse("2001:4860:4860::8888\n")
        return FakeResponse("8.8.8.8\n")

    assert detect_public_ip("ipv4", endpoints=["https://one.example", "https://two.example"], opener=opener) == "8.8.8.8"
    assert calls == ["https://one.example", "https://two.example"]


def test_ipv6_resolver_accepts_only_ipv6():
    def opener(request, timeout):
        return FakeResponse("8.8.8.8\n")

    with pytest.raises(IPDetectionError):
        detect_public_ip("ipv6", endpoints=["https://one.example"], opener=opener)
