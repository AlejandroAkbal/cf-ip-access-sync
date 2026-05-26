from __future__ import annotations

import ipaddress
from typing import Callable, Iterable
from urllib.request import Request, urlopen


IPV4_ENDPOINTS = (
    "https://api.ipify.org",
    "https://ipv4.icanhazip.com",
    "https://checkip.amazonaws.com",
)
IPV6_ENDPOINTS = (
    "https://api6.ipify.org",
    "https://ipv6.icanhazip.com",
)


class IPDetectionError(RuntimeError):
    """Raised when a public IP address cannot be detected or validated."""


UrlOpen = Callable[..., object]


def validate_public_ip(value: str, version: int | None) -> str:
    candidate = value.strip()
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise IPDetectionError(f"invalid IP address: {candidate!r}") from exc
    if version is not None and ip.version != version:
        raise IPDetectionError(f"expected IPv{version}, got IPv{ip.version}")
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or not ip.is_global
    ):
        raise IPDetectionError(f"not a public global IP address: {candidate}")
    return str(ip)


def detect_public_ip(
    family: str,
    endpoints: Iterable[str] | None = None,
    opener: UrlOpen = urlopen,
    timeout: float = 5.0,
) -> str:
    if family == "ipv4":
        version = 4
        selected_endpoints = tuple(endpoints or IPV4_ENDPOINTS)
    elif family == "ipv6":
        version = 6
        selected_endpoints = tuple(endpoints or IPV6_ENDPOINTS)
    else:
        raise IPDetectionError(f"unsupported IP family: {family}")

    errors: list[str] = []
    for endpoint in selected_endpoints:
        try:
            request = Request(endpoint, headers={"User-Agent": "cf-ip-access-sync/0.1"})
            with opener(request, timeout=timeout) as response:
                body = response.read(128).decode("ascii", errors="replace")
            return validate_public_ip(body, version)
        except Exception as exc:  # noqa: BLE001 - all resolver failures should fail over.
            errors.append(f"{endpoint}: {exc}")
    joined = "; ".join(errors) if errors else "no endpoints configured"
    raise IPDetectionError(f"could not detect public {family} address: {joined}")
