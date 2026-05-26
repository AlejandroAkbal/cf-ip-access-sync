from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "https://api.cloudflare.com/client/v4"


class CloudflareAPIError(RuntimeError):
    """Raised for HTTP, network, or Cloudflare API failures."""


@dataclass(slots=True)
class AccessRule:
    id: str
    mode: str
    configuration: dict[str, Any]
    notes: str = ""
    created_on: str | None = None
    modified_on: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AccessRule":
        return cls(
            id=str(data.get("id", "")),
            mode=str(data.get("mode", "")),
            configuration=dict(data.get("configuration") or {}),
            notes=str(data.get("notes") or ""),
            created_on=data.get("created_on"),
            modified_on=data.get("modified_on"),
            raw=data,
        )

    @property
    def target(self) -> str:
        return str(self.configuration.get("target", ""))

    @property
    def value(self) -> str:
        return str(self.configuration.get("value", ""))


def build_access_rule_payload(target: str, value: str, mode: str, notes: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "configuration": {
            "target": target,
            "value": value,
        },
        "notes": notes,
    }


class CloudflareClient:
    def __init__(self, token: str, base_url: str = API_BASE_URL, timeout: float = 15.0):
        if not token:
            raise CloudflareAPIError("Cloudflare API token is missing")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def list_access_rules(
        self,
        account_id: str,
        notes: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[AccessRule]:
        rules: list[AccessRule] = []
        current_page = page
        while True:
            query: dict[str, Any] = {"page": current_page, "per_page": per_page}
            if notes:
                query["notes"] = notes
            response = self._request(
                "GET",
                f"/accounts/{account_id}/firewall/access_rules/rules",
                query=query,
            )
            batch = [AccessRule.from_api(item) for item in response.get("result") or []]
            rules.extend(batch)
            info = response.get("result_info") or {}
            total_count = info.get("total_count")
            if total_count is not None:
                if len(rules) >= int(total_count):
                    break
            elif len(batch) < per_page:
                break
            if not batch:
                break
            current_page += 1
        return rules

    def create_access_rule(self, account_id: str, target: str, value: str, mode: str, notes: str) -> AccessRule:
        response = self._request(
            "POST",
            f"/accounts/{account_id}/firewall/access_rules/rules",
            payload=build_access_rule_payload(target, value, mode, notes),
        )
        return AccessRule.from_api(response.get("result") or {})

    def update_access_rule(
        self,
        account_id: str,
        rule_id: str,
        target: str,
        value: str,
        mode: str,
        notes: str,
    ) -> AccessRule:
        response = self._request(
            "PATCH",
            f"/accounts/{account_id}/firewall/access_rules/rules/{rule_id}",
            payload=build_access_rule_payload(target, value, mode, notes),
        )
        return AccessRule.from_api(response.get("result") or {})

    def delete_access_rule(self, account_id: str, rule_id: str) -> str:
        response = self._request("DELETE", f"/accounts/{account_id}/firewall/access_rules/rules/{rule_id}")
        result = response.get("result") or {}
        if isinstance(result, dict):
            return str(result.get("id") or rule_id)
        return rule_id

    def verify_token(self) -> bool:
        try:
            self._request("GET", "/user/tokens/verify")
        except CloudflareAPIError:
            return False
        return True

    def _request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        body = None
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": "cf-ip-access-sync/0.1",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise CloudflareAPIError(f"Cloudflare HTTP {exc.code}: {_format_error_body(error_body)}") from exc
        except URLError as exc:
            raise CloudflareAPIError(f"Cloudflare network error: {exc.reason}") from exc
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise CloudflareAPIError("Cloudflare returned non-JSON response") from exc
        if not data.get("success", False):
            raise CloudflareAPIError(f"Cloudflare API error: {_format_cloudflare_errors(data)}")
        return data


def _format_error_body(body: str) -> str:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body[:500] or "empty response"
    return _format_cloudflare_errors(data)


def _format_cloudflare_errors(data: dict[str, Any]) -> str:
    errors = data.get("errors") or []
    if not errors:
        return "success=false"
    parts = []
    for error in errors:
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message") or "unknown error"
            parts.append(f"{code}: {message}" if code is not None else str(message))
        else:
            parts.append(str(error))
    return "; ".join(parts)
