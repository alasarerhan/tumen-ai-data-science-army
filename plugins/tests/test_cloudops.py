"""Tests for M16 — CloudOps tools and agents (IaCAgent, ContainerizationAgent, CICDAgent).

Tool tests call ``.func()`` directly (no LLM required).
Agent construction tests use a deterministic FakeChatModel stub.
"""
from __future__ import annotations

import json
from typing import Any, Dict

import pytest


# ===========================================================================
# Fake LLM helper
# ===========================================================================


def _fake_llm():
    """Minimal stub satisfying graph construction — no API key needed."""
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage as LCAIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class FakeChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "fake"

        def _generate(self, messages, stop=None, run_manager=None, **kw) -> ChatResult:
            return ChatResult(
                generations=[ChatGeneration(message=LCAIMessage(content="Done."))]
            )

        def bind_tools(self, tools, **kw):
            return self

    return FakeChatModel()


# ===========================================================================
# scaffold_terraform_resource
# ===========================================================================


def test_scaffold_known_aws_instance():
    from ai_data_science_team.tools.cloudops import scaffold_terraform_resource

    text, artifact = scaffold_terraform_resource.func(
        resource_type="aws_instance",
        name="web_server",
        provider="aws",
        region="us-east-1",
        size="small",
    )
    assert "aws_instance" in text
    assert "web_server" in text
    assert artifact["known_template"] is True
    assert artifact["resource_type"] == "aws_instance"


def test_scaffold_known_aws_s3_bucket():
    from ai_data_science_team.tools.cloudops import scaffold_terraform_resource

    text, artifact = scaffold_terraform_resource.func(
        resource_type="aws_s3_bucket",
        name="my_bucket",
        provider="aws",
    )
    assert "aws_s3_bucket" in text
    assert "my_bucket" in text
    assert artifact["known_template"] is True


def test_scaffold_generic_fallback():
    from ai_data_science_team.tools.cloudops import scaffold_terraform_resource

    text, artifact = scaffold_terraform_resource.func(
        resource_type="custom_exotic_resource",
        name="test_res",
        provider="custom",
    )
    assert "custom_exotic_resource" in text
    assert artifact["known_template"] is False


def test_scaffold_artifact_keys():
    from ai_data_science_team.tools.cloudops import scaffold_terraform_resource

    _, artifact = scaffold_terraform_resource.func(
        resource_type="aws_lambda_function",
        name="handler",
    )
    for key in ("resource_type", "name", "provider", "region", "size", "hcl", "known_template"):
        assert key in artifact, f"Missing artifact key: {key}"


def test_scaffold_hcl_contains_tags():
    from ai_data_science_team.tools.cloudops import scaffold_terraform_resource

    _, artifact = scaffold_terraform_resource.func(
        resource_type="aws_instance",
        name="app_server",
    )
    assert "tags" in artifact["hcl"]


# ===========================================================================
# list_terraform_providers
# ===========================================================================


def test_list_providers_returns_known_providers():
    from ai_data_science_team.tools.cloudops import list_terraform_providers

    text, artifact = list_terraform_providers.func()
    providers = artifact["providers"]
    assert isinstance(providers, dict)
    for expected in ("aws", "azurerm", "google", "kubernetes"):
        assert expected in providers


def test_list_providers_text_contains_provider_names():
    from ai_data_science_team.tools.cloudops import list_terraform_providers

    text, _ = list_terraform_providers.func()
    assert "aws" in text
    assert "google" in text


# ===========================================================================
# estimate_monthly_cost
# ===========================================================================


def test_estimate_cost_known_resource():
    from ai_data_science_team.tools.cloudops import estimate_monthly_cost

    text, artifact = estimate_monthly_cost.func(
        resource_type="aws_instance",
        size="small",
        region="us-east-1",
    )
    assert artifact["known"] is True
    assert artifact["estimated_usd_monthly"] is not None
    assert artifact["estimated_usd_monthly"] > 0
    assert "$" in text


def test_estimate_cost_large_size():
    from ai_data_science_team.tools.cloudops import estimate_monthly_cost

    _, artifact_small = estimate_monthly_cost.func(resource_type="aws_instance", size="small")
    _, artifact_large = estimate_monthly_cost.func(resource_type="aws_instance", size="large")
    assert artifact_large["estimated_usd_monthly"] > artifact_small["estimated_usd_monthly"]


def test_estimate_cost_unknown_resource():
    from ai_data_science_team.tools.cloudops import estimate_monthly_cost

    text, artifact = estimate_monthly_cost.func(resource_type="exotic_service_xyz", size="small")
    assert artifact["known"] is False
    assert artifact["estimated_usd_monthly"] is None


def test_estimate_cost_artifact_keys():
    from ai_data_science_team.tools.cloudops import estimate_monthly_cost

    _, artifact = estimate_monthly_cost.func(resource_type="aws_rds_instance", size="medium")
    for key in ("resource_type", "size", "region", "estimated_usd_monthly", "known"):
        assert key in artifact


# ===========================================================================
# validate_hcl_syntax
# ===========================================================================

_VALID_HCL = '''\
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = "t3.small"
  tags = {
    Name = "web"
  }
}'''

_UNCLOSED_BRACE_HCL = '''\
resource "aws_instance" "web" {
  ami = var.ami_id
  tags = {
    Name = "web"
'''

_UNCLOSED_STRING_HCL = '''\
resource "aws_instance" "web" {
  ami = var.ami_id
  name = "not closed
}'''


def test_validate_hcl_valid():
    from ai_data_science_team.tools.cloudops import validate_hcl_syntax

    text, artifact = validate_hcl_syntax.func(hcl=_VALID_HCL)
    assert artifact["valid"] is True
    assert len(artifact["errors"]) == 0
    assert "✅" in text


def test_validate_hcl_unclosed_brace():
    from ai_data_science_team.tools.cloudops import validate_hcl_syntax

    text, artifact = validate_hcl_syntax.func(hcl=_UNCLOSED_BRACE_HCL)
    assert artifact["valid"] is False
    assert len(artifact["errors"]) > 0
    assert "❌" in text


def test_validate_hcl_unclosed_string():
    from ai_data_science_team.tools.cloudops import validate_hcl_syntax

    text, artifact = validate_hcl_syntax.func(hcl=_UNCLOSED_STRING_HCL)
    assert artifact["valid"] is False
    assert any("unclosed" in e.lower() or "odd" in e.lower() for e in artifact["errors"])


def test_validate_hcl_artifact_keys():
    from ai_data_science_team.tools.cloudops import validate_hcl_syntax

    _, artifact = validate_hcl_syntax.func(hcl=_VALID_HCL)
    for key in ("valid", "errors", "warnings", "brace_depth_final"):
        assert key in artifact


# ===========================================================================
# generate_dockerfile
# ===========================================================================


def test_dockerfile_python_base_image():
    from ai_data_science_team.tools.cloudops import generate_dockerfile

    text, artifact = generate_dockerfile.func(
        language="python",
        version="3.11",
        port=8000,
    )
    assert "python:3.11" in artifact["base_image"]
    assert "FROM python" in text


def test_dockerfile_node_base_image():
    from ai_data_science_team.tools.cloudops import generate_dockerfile

    _, artifact = generate_dockerfile.func(language="node", version="20", port=3000)
    assert "node:20" in artifact["base_image"]
    assert artifact["port"] == 3000


def test_dockerfile_exposes_port():
    from ai_data_science_team.tools.cloudops import generate_dockerfile

    text, artifact = generate_dockerfile.func(language="python", version="3.12", port=5000)
    assert "EXPOSE 5000" in artifact["dockerfile"]
    assert artifact["port"] == 5000


def test_dockerfile_custom_start_command():
    from ai_data_science_team.tools.cloudops import generate_dockerfile

    _, artifact = generate_dockerfile.func(
        language="python",
        version="3.11",
        start_command="gunicorn -w 4 app:app",
    )
    assert artifact["start_command"] == "gunicorn -w 4 app:app"


def test_dockerfile_artifact_keys():
    from ai_data_science_team.tools.cloudops import generate_dockerfile

    _, artifact = generate_dockerfile.func(language="go", version="1.21")
    for key in ("language", "version", "port", "app_dir", "base_image", "dockerfile"):
        assert key in artifact


# ===========================================================================
# generate_docker_compose_yaml
# ===========================================================================

_SERVICES_JSON = json.dumps([
    {"name": "api", "image": "myapp:1.0", "port": 8000, "env": {"DEBUG": "false"}},
    {"name": "db", "image": "postgres:15", "port": 5432},
])


def test_docker_compose_service_count():
    from ai_data_science_team.tools.cloudops import generate_docker_compose_yaml

    _, artifact = generate_docker_compose_yaml.func(services_json=_SERVICES_JSON)
    assert artifact["service_count"] == 2
    assert "api" in artifact["service_names"]
    assert "db" in artifact["service_names"]


def test_docker_compose_ports_in_yaml():
    from ai_data_science_team.tools.cloudops import generate_docker_compose_yaml

    _, artifact = generate_docker_compose_yaml.func(services_json=_SERVICES_JSON)
    yaml = artifact["compose_yaml"]
    assert "8000" in yaml
    assert "5432" in yaml


def test_docker_compose_env_in_yaml():
    from ai_data_science_team.tools.cloudops import generate_docker_compose_yaml

    _, artifact = generate_docker_compose_yaml.func(services_json=_SERVICES_JSON)
    assert "DEBUG" in artifact["compose_yaml"]


def test_docker_compose_invalid_json():
    from ai_data_science_team.tools.cloudops import generate_docker_compose_yaml

    text, artifact = generate_docker_compose_yaml.func(services_json="not-valid-json{")
    assert artifact["valid"] is False
    assert "❌" in text


# ===========================================================================
# generate_k8s_manifest
# ===========================================================================


def test_k8s_deployment_manifest():
    from ai_data_science_team.tools.cloudops import generate_k8s_manifest

    text, artifact = generate_k8s_manifest.func(
        resource_kind="Deployment",
        name="my-app",
        image="myapp:1.0",
        replicas=3,
        port=8080,
    )
    assert artifact["valid"] is True
    assert "Deployment" in artifact["yaml"]
    assert "replicas: 3" in artifact["yaml"]
    assert "my-app" in artifact["yaml"]


def test_k8s_service_manifest():
    from ai_data_science_team.tools.cloudops import generate_k8s_manifest

    _, artifact = generate_k8s_manifest.func(
        resource_kind="Service",
        name="my-svc",
        port=8080,
    )
    assert artifact["valid"] is True
    assert "Service" in artifact["yaml"]
    assert "8080" in artifact["yaml"]


def test_k8s_namespace_manifest():
    from ai_data_science_team.tools.cloudops import generate_k8s_manifest

    _, artifact = generate_k8s_manifest.func(
        resource_kind="Namespace",
        name="production",
    )
    assert artifact["valid"] is True
    assert "production" in artifact["yaml"]


def test_k8s_unknown_kind_returns_error():
    from ai_data_science_team.tools.cloudops import generate_k8s_manifest

    text, artifact = generate_k8s_manifest.func(
        resource_kind="UnknownKind",
        name="test",
    )
    assert artifact["valid"] is False
    assert "❌" in text


def test_k8s_namespace_in_manifest():
    from ai_data_science_team.tools.cloudops import generate_k8s_manifest

    _, artifact = generate_k8s_manifest.func(
        resource_kind="Deployment",
        name="worker",
        namespace="production",
    )
    assert "production" in artifact["yaml"]


# ===========================================================================
# generate_github_actions_workflow
# ===========================================================================


def test_github_actions_contains_checkout():
    from ai_data_science_team.tools.cloudops import generate_github_actions_workflow

    text, artifact = generate_github_actions_workflow.func(
        trigger="push",
        branches="main",
        python_version="3.11",
    )
    assert "actions/checkout" in artifact["yaml"]


def test_github_actions_python_version():
    from ai_data_science_team.tools.cloudops import generate_github_actions_workflow

    _, artifact = generate_github_actions_workflow.func(
        python_version="3.12",
    )
    assert "3.12" in artifact["yaml"]
    assert artifact["python_version"] == "3.12"


def test_github_actions_custom_test_command():
    from ai_data_science_team.tools.cloudops import generate_github_actions_workflow

    _, artifact = generate_github_actions_workflow.func(
        test_command="python -m pytest -x -q",
    )
    assert "python -m pytest" in artifact["yaml"]


def test_github_actions_multi_trigger():
    from ai_data_science_team.tools.cloudops import generate_github_actions_workflow

    _, artifact = generate_github_actions_workflow.func(trigger="push,pull_request")
    assert "push" in artifact["triggers"]
    assert "pull_request" in artifact["triggers"]


def test_github_actions_artifact_keys():
    from ai_data_science_team.tools.cloudops import generate_github_actions_workflow

    _, artifact = generate_github_actions_workflow.func()
    for key in ("workflow_name", "triggers", "branches", "python_version", "yaml"):
        assert key in artifact


# ===========================================================================
# generate_gitlab_ci_pipeline
# ===========================================================================


def test_gitlab_ci_contains_stages():
    from ai_data_science_team.tools.cloudops import generate_gitlab_ci_pipeline

    text, artifact = generate_gitlab_ci_pipeline.func(
        stages="install,test,build",
    )
    assert "install" in artifact["yaml"]
    assert "test" in artifact["yaml"]
    assert "build" in artifact["yaml"]


def test_gitlab_ci_docker_image_in_yaml():
    from ai_data_science_team.tools.cloudops import generate_gitlab_ci_pipeline

    _, artifact = generate_gitlab_ci_pipeline.func(
        docker_image="python:3.12-slim",
    )
    assert "python:3.12-slim" in artifact["yaml"]


def test_gitlab_ci_test_command_in_yaml():
    from ai_data_science_team.tools.cloudops import generate_gitlab_ci_pipeline

    _, artifact = generate_gitlab_ci_pipeline.func(
        test_command="pytest --tb=short",
    )
    assert "pytest --tb=short" in artifact["yaml"]


def test_gitlab_ci_deploy_stage_manual():
    from ai_data_science_team.tools.cloudops import generate_gitlab_ci_pipeline

    _, artifact = generate_gitlab_ci_pipeline.func(
        stages="test,deploy",
    )
    assert "manual" in artifact["yaml"]


def test_gitlab_ci_artifact_keys():
    from ai_data_science_team.tools.cloudops import generate_gitlab_ci_pipeline

    _, artifact = generate_gitlab_ci_pipeline.func()
    for key in ("stages", "docker_image", "test_command", "yaml"):
        assert key in artifact


# ===========================================================================
# Agent construction tests
# ===========================================================================


def test_iac_agent_instantiation():
    from ai_data_science_team.agents.cloudops_agents import IaCAgent

    agent = IaCAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_artifacts")
    assert hasattr(agent, "get_ai_message")
    assert hasattr(agent, "get_tool_calls")


def test_iac_agent_nodes_present():
    from ai_data_science_team.agents.cloudops_agents import IaCAgent

    agent = IaCAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)
    assert any("post" in n for n in node_names)


def test_iac_agent_state_before_invoke():
    from ai_data_science_team.agents.cloudops_agents import IaCAgent

    agent = IaCAgent(model=_fake_llm())
    assert agent.get_ai_message() is None
    assert agent.get_artifacts() == {}
    assert agent.get_tool_calls() == []


def test_iac_agent_update_params_rebuilds_graph():
    from ai_data_science_team.agents.cloudops_agents import IaCAgent

    agent = IaCAgent(model=_fake_llm())
    original = agent._compiled_graph
    agent.update_params(system_prompt="Override prompt.")
    assert agent._compiled_graph is not original


def test_containerization_agent_instantiation():
    from ai_data_science_team.agents.cloudops_agents import ContainerizationAgent

    agent = ContainerizationAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")


def test_containerization_agent_nodes_present():
    from ai_data_science_team.agents.cloudops_agents import ContainerizationAgent

    agent = ContainerizationAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)


def test_containerization_agent_state_before_invoke():
    from ai_data_science_team.agents.cloudops_agents import ContainerizationAgent

    agent = ContainerizationAgent(model=_fake_llm())
    assert agent.get_ai_message() is None
    assert agent.get_artifacts() == {}


def test_cicd_agent_instantiation():
    from ai_data_science_team.agents.cloudops_agents import CICDAgent

    agent = CICDAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_ai_message")


def test_cicd_agent_nodes_present():
    from ai_data_science_team.agents.cloudops_agents import CICDAgent

    agent = CICDAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)
    assert any("post" in n for n in node_names)


def test_cicd_agent_update_params_rebuilds_graph():
    from ai_data_science_team.agents.cloudops_agents import CICDAgent

    agent = CICDAgent(model=_fake_llm())
    original = agent._compiled_graph
    agent.update_params(system_prompt="Another prompt.")
    assert agent._compiled_graph is not original


def test_all_three_agents_have_distinct_graphs():
    from ai_data_science_team.agents.cloudops_agents import (
        IaCAgent, ContainerizationAgent, CICDAgent
    )

    llm = _fake_llm()
    iac = IaCAgent(model=llm)
    container = ContainerizationAgent(model=llm)
    cicd = CICDAgent(model=llm)

    # Each agent wraps a different compiled graph
    assert iac._compiled_graph is not container._compiled_graph
    assert container._compiled_graph is not cicd._compiled_graph
