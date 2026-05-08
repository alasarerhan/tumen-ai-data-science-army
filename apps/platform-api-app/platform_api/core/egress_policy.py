from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _parse_allowed_hosts(allowed_hosts: str) -> list[str]:
    return [host.strip().lower() for host in allowed_hosts.split(",") if host.strip()]


def _host_matches(candidate_host: str, allowed_host: str) -> bool:
    if candidate_host == allowed_host:
        return True
    return candidate_host.endswith(f".{allowed_host}")


def is_url_host_allowed(url: str, allowed_hosts: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    for allowed in _parse_allowed_hosts(allowed_hosts):
        if _host_matches(host, allowed):
            return True
    return False


def enforce_egress_policy(
    *,
    url: str,
    allowed_hosts: str,
    strict_mode: bool,
    purpose: str,
) -> bool:
    """Return True when allowed; raise ValueError in strict mode."""
    allowed = is_url_host_allowed(url, allowed_hosts)
    if allowed:
        return True

    event = {
        "event": "egress_policy_violation",
        "purpose": purpose,
        "url": url,
        "strict_mode": strict_mode,
    }
    logger.warning("%s", event)

    if strict_mode:
        raise ValueError(f"Egress target is not allowed for {purpose}")
    return False

