"""OpenAI-compatible LLM test helpers.

The integration + e2e test files (plugins/tests/test_e2e_*.py and
test_integration_*.py) need a real LLM to run. This module centralises
the API-key lookup and chat-model construction so each test file is a
one-line import.

Defaults target OpenCode Zen (https://opencode.ai/zen) — an OpenAI-
compatible gateway that serves curated coding models. The model is
DeepSeek V4 Flash (fast + cheap + tool-calling).

Resolves API keys in this order:
  1. `OPENCODE_API_KEY`        — preferred (OpenCode Zen)
  2. `OPENAI_API_KEY`          — fallback (any OpenAI-compatible provider)
  3. `GEMINI_API_KEY`          — last-resort (Google AI Studio)

If none are set, the helpers raise a pytest.skip() so the e2e/integration
tests pass through cleanly when the user has no key at all.
"""
from __future__ import annotations

import os
from typing import Optional

import pytest

# OpenCode Zen OpenAI-compatible endpoint.
DEFAULT_BASE_URL = os.getenv("LLM_BASE_URL", "https://opencode.ai/zen/v1")

# Default model — override via LLM_MODEL env var.
DEFAULT_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")


def get_api_key() -> Optional[str]:
    """Return the first non-empty key (OPENCODE_API_KEY → OPENAI_API_KEY → GEMINI_API_KEY)."""
    for var in ("OPENCODE_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        v = os.getenv(var)
        if v:
            return v
    return None


def require_key():
    """Pytest helper — skip the test if no API key is configured."""
    if not get_api_key():
        pytest.skip(
            "No LLM API key set (expected one of OPENCODE_API_KEY, "
            "OPENAI_API_KEY, or GEMINI_API_KEY) — skipping integration/e2e test"
        )


def make_chat_model(**overrides):
    """Return a ``langchain_openai.ChatOpenAI`` instance.

    Pass-through kwargs let each test tweak temperature / max_tokens
    without duplicating the URL / model boilerplate.
    """
    from langchain_openai import ChatOpenAI

    api_key = get_api_key()
    if not api_key:
        require_key()  # raises pytest.skip

    kwargs = {
        "model": DEFAULT_MODEL,
        "api_key": api_key,
        "base_url": DEFAULT_BASE_URL,
        "temperature": 0,
        "max_tokens": 1024,
    }
    kwargs.update(overrides)
    return ChatOpenAI(**kwargs)


# Convenience: a pre-built skipif marker that tests can apply with
# ``@skip_no_key``.
skip_no_key = pytest.mark.skipif(
    not get_api_key(),
    reason=(
        "No LLM API key set (expected one of OPENCODE_API_KEY, "
        "OPENAI_API_KEY, or GEMINI_API_KEY) — skipping integration/e2e test"
    ),
)
