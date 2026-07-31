"""Safe, provider-neutral endpoint validation for model connection checks."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit
from typing import Optional


class EndpointPolicyError(ValueError):
    """Raised when a configured provider endpoint is unsafe or malformed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _is_non_public_host(hostname: str) -> bool:
    normalized = hostname.strip("[]").lower().rstrip(".")
    if normalized in {"localhost", "localhost.localdomain"}:
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized.endswith(".local")
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )


def validate_endpoint_url(
    value: Optional[str],
    *,
    allow_local: bool = False,
) -> Optional[str]:
    """Validate and normalize an endpoint without making a network request.

    DNS resolution and egress enforcement belong to the deployment boundary;
    this function rejects dangerous schemes, userinfo and obvious private
    destinations before an adapter is allowed to make a request.
    """

    if value is None or not value.strip():
        return None
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise EndpointPolicyError("endpoint.scheme_not_allowed")
    if parsed.username or parsed.password:
        raise EndpointPolicyError("endpoint.userinfo_not_allowed")
    if not parsed.hostname:
        raise EndpointPolicyError("endpoint.host_required")
    if parsed.query or parsed.fragment:
        raise EndpointPolicyError("endpoint.query_or_fragment_not_allowed")
    if not allow_local and _is_non_public_host(parsed.hostname):
        raise EndpointPolicyError("endpoint.private_address_not_allowed")
    if parsed.scheme.lower() == "http" and not allow_local:
        raise EndpointPolicyError("endpoint.https_required")
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise EndpointPolicyError("endpoint.port_invalid")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))


def endpoint_summary(value: Optional[str]) -> Optional[str]:
    """Return a non-secret display value containing only scheme/host/path."""

    normalized = validate_endpoint_url(value, allow_local=True)
    if normalized is None:
        return None
    parsed = urlsplit(normalized)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
