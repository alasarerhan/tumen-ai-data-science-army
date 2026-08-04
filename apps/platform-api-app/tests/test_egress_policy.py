from __future__ import annotations

import pytest

from platform_api.core.egress_policy import enforce_egress_policy, is_url_host_allowed


def test_is_url_host_allowed_supports_exact_and_subdomain():
    assert is_url_host_allowed(
        "https://accounts.google.com/.well-known/jwks.json", "accounts.google.com"
    )
    assert is_url_host_allowed("https://sub.example.com/path", "example.com")
    assert not is_url_host_allowed("https://evil-example.com/path", "example.com")


def test_enforce_egress_policy_raises_in_strict_mode():
    with pytest.raises(ValueError):
        enforce_egress_policy(
            url="https://untrusted.example.net/jwks",
            allowed_hosts="accounts.google.com",
            strict_mode=True,
            purpose="oidc_jwks_fetch",
        )


def test_enforce_egress_policy_allows_when_non_strict():
    allowed = enforce_egress_policy(
        url="https://untrusted.example.net/file",
        allowed_hosts="accounts.google.com",
        strict_mode=False,
        purpose="artifact_redirect",
    )
    assert allowed is False
