"""
M16 - CloudOps Agent Ekibi TG2 Entegrasyon Testleri
=====================================================
Gercek LLM API (OpenAI) ile uctan-uca calisir.
Calistirmak icin:
    python -m pytest tests/test_integration_m16.py -v -m integration
Atlamak icin:
    python -m pytest tests/ -v -m "not integration"
"""

import pytest
from _llm import make_chat_model, skip_no_key

pytestmark = pytest.mark.integration


langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping integration tests",
)


def _inv(agent, **kw):
    """Invoke agent; skip gracefully if OpenAI quota is exhausted."""
    try:
        agent.invoke_agent(**kw)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run integration tests")
        raise


@pytest.fixture(scope="module")
def llm():
    return make_chat_model(temperature=0, max_tokens=400)


# ---------------------------------------------------------------------------
# IaCAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_iac_agent_terraform_resource(llm):
    """IaCAgent should scaffold a Terraform resource and return a non-empty AI message."""
    from ai_data_science_team.agents.cloudops_agents import IaCAgent

    agent = IaCAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Scaffold a minimal Terraform AWS S3 bucket resource named my-data-bucket "
            "in us-east-1. Use the aws provider."
        ),
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_iac_agent_artifacts(llm):
    """IaCAgent should return a dict from get_artifacts()."""
    from ai_data_science_team.agents.cloudops_agents import IaCAgent

    agent = IaCAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Estimate the monthly cost for an AWS t3.small EC2 instance running 24/7 in eu-west-1."
        ),
    )
    assert isinstance(agent.get_artifacts(), dict)


@skip_no_key
def test_iac_agent_tool_calls(llm):
    """IaCAgent should record at least one tool call."""
    from ai_data_science_team.agents.cloudops_agents import IaCAgent

    agent = IaCAgent(model=llm)
    _inv(agent, user_instructions="List the available Terraform providers and suggest one for GCP.")
    tool_calls = agent.get_tool_calls()
    assert isinstance(tool_calls, list) and len(tool_calls) > 0


# ---------------------------------------------------------------------------
# ContainerizationAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_containerization_agent_dockerfile(llm):
    """ContainerizationAgent should generate a Dockerfile."""
    from ai_data_science_team.agents.cloudops_agents import ContainerizationAgent

    agent = ContainerizationAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Generate a Dockerfile for a FastAPI Python 3.11 application. "
            "The entry point is uvicorn main:app --host 0.0.0.0 --port 8080."
        ),
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_containerization_agent_tool_calls(llm):
    """ContainerizationAgent should invoke at least one code-generation tool."""
    from ai_data_science_team.agents.cloudops_agents import ContainerizationAgent

    agent = ContainerizationAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Create a minimal docker-compose.yml for a FastAPI service and a PostgreSQL database."
        ),
    )
    assert isinstance(agent.get_tool_calls(), list) and len(agent.get_tool_calls()) > 0


# ---------------------------------------------------------------------------
# CICDAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_cicd_agent_github_actions(llm):
    """CICDAgent should generate a GitHub Actions workflow."""
    from ai_data_science_team.agents.cloudops_agents import CICDAgent

    agent = CICDAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Generate a GitHub Actions CI workflow for a Python project that runs pytest on push to main."
        ),
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_cicd_agent_tool_calls(llm):
    """CICDAgent should invoke at least one pipeline-generation tool."""
    from ai_data_science_team.agents.cloudops_agents import CICDAgent

    agent = CICDAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Create a GitLab CI/CD pipeline for a Docker-based Python project with build and test stages."
        ),
    )
    assert isinstance(agent.get_tool_calls(), list) and len(agent.get_tool_calls()) > 0
