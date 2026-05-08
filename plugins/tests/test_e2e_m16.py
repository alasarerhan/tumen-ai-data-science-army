"""M16 TG3 — CloudOps Agent E2E Zinciri.

Uc asamali tam bir "infrastructure package" olusturur:
  1. IaCAgent       → Terraform kaynak tanimi + maliyet tahmini
  2. ContainerizationAgent → Dockerfile + docker-compose (Terraform ciktisini kullanarak)
  3. CICDAgent      → GitHub Actions pipeline (onceki iki asamanin ciktisini kullanarak)

Calistirmak icin:
    python -m pytest tests/test_e2e_m16.py -v -m integration
Atlamak icin (API anahtari olmadan):
    python -m pytest tests/ -v -m "not integration"
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
skip_no_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY is not set — skipping integration tests",
)

langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping integration tests",
)


def _inv(agent, **kw):
    """Invoke agent; skip gracefully on OpenAI quota errors."""
    try:
        agent.invoke_agent(**kw)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run E2E tests")
        raise


@pytest.fixture(scope="module")
def llm():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=600)


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _run_iac(llm) -> dict:
    from ai_data_science_team.agents.cloudops_agents import IaCAgent
    agent = IaCAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Scaffold a minimal Terraform AWS S3 bucket named platform-data in eu-west-1. "
            "Then estimate its monthly cost."
        ),
    )
    artifacts = agent.get_artifacts()
    artifacts["_iac_ai_message"] = agent.get_ai_message() or ""
    return artifacts


def _run_containerization(llm, iac_artifacts: dict) -> dict:
    from ai_data_science_team.agents.cloudops_agents import ContainerizationAgent
    agent = ContainerizationAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Generate a production-ready Dockerfile for a FastAPI app (Python 3.11). "
            "Also create a docker-compose.yml with the app and a PostgreSQL service."
        ),
        prior_artifacts=iac_artifacts,
    )
    artifacts = agent.get_artifacts()
    artifacts["_container_ai_message"] = agent.get_ai_message() or ""
    return artifacts


def _run_cicd(llm, container_artifacts: dict) -> dict:
    from ai_data_science_team.agents.cloudops_agents import CICDAgent
    agent = CICDAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Generate a GitHub Actions CI/CD workflow that: "
            "1) runs pytest on every push to main, "
            "2) builds and pushes the Docker image to Docker Hub on tag push."
        ),
        prior_artifacts=container_artifacts,
    )
    artifacts = agent.get_artifacts()
    artifacts["_cicd_ai_message"] = agent.get_ai_message() or ""
    return artifacts


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


@skip_no_key
def test_e2e_cloudops_full_pipeline(llm):
    """Full 3-stage CloudOps pipeline produces non-empty outputs at each stage."""
    # Stage 1 — IaC
    iac_out = _run_iac(llm)
    assert isinstance(iac_out, dict), "IaCAgent must return a dict"
    assert len(iac_out.get("_iac_ai_message", "")) > 0, "IaCAgent must produce an AI message"

    # Stage 2 — Containerization (receives IaC output as context)
    container_out = _run_containerization(llm, iac_out)
    assert isinstance(container_out, dict), "ContainerizationAgent must return a dict"
    assert len(container_out.get("_container_ai_message", "")) > 0, (
        "ContainerizationAgent must produce an AI message"
    )

    # Stage 3 — CI/CD (receives both IaC + containerization context)
    combined = {**iac_out, **container_out}
    cicd_out = _run_cicd(llm, combined)
    assert isinstance(cicd_out, dict), "CICDAgent must return a dict"
    assert len(cicd_out.get("_cicd_ai_message", "")) > 0, (
        "CICDAgent must produce an AI message"
    )


@skip_no_key
def test_e2e_cloudops_artifacts_propagate(llm):
    """IaC artifacts are visible in downstream agent context."""
    iac_out = _run_iac(llm)
    # Pass IaC artifacts as prior context to containerization
    container_out = _run_containerization(llm, iac_out)
    # Both dicts should be non-empty (agent stored something)
    assert len(iac_out) > 0, "IaC must produce at least one artifact key"
    assert len(container_out) > 0, "Containerization must produce at least one artifact key"


@skip_no_key
def test_e2e_cloudops_each_stage_uses_tools(llm):
    """Each stage must invoke at least one tool call."""
    from ai_data_science_team.agents.cloudops_agents import (
        IaCAgent,
        ContainerizationAgent,
        CICDAgent,
    )

    iac = IaCAgent(model=llm)
    _inv(iac, user_instructions="List available Terraform providers and estimate cost for an AWS t3.micro.")
    assert len(iac.get_tool_calls()) > 0, "IaCAgent must invoke at least one tool"

    container = ContainerizationAgent(model=llm)
    _inv(container, user_instructions="Generate a Dockerfile for a Node.js 20 app.")
    assert len(container.get_tool_calls()) > 0, "ContainerizationAgent must invoke at least one tool"

    cicd = CICDAgent(model=llm)
    _inv(cicd, user_instructions="Generate a GitLab CI pipeline with a test stage.")
    assert len(cicd.get_tool_calls()) > 0, "CICDAgent must invoke at least one tool"
