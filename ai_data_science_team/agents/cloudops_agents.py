from __future__ import annotations

"""CloudOps Agent Ekibi — Infrastructure as Code, Containerization, CI/CD (M16).

Three specialist agents backed by pure-Python code-generation tools:

``IaCAgent``
    Generates and validates Terraform HCL, estimates cloud costs, and guides
    infrastructure provisioning decisions.  Uses tools:
    ``scaffold_terraform_resource``, ``list_terraform_providers``,
    ``estimate_monthly_cost``, ``validate_hcl_syntax``.

``ContainerizationAgent``
    Creates Dockerfiles, docker-compose files, and Kubernetes manifests.  Uses
    tools: ``generate_dockerfile``, ``generate_docker_compose_yaml``,
    ``generate_k8s_manifest``.

``CICDAgent``
    Builds GitHub Actions and GitLab CI pipeline YAML files.  Uses tools:
    ``generate_github_actions_workflow``, ``generate_gitlab_ci_pipeline``.

Example usage::

    from langchain_openai import ChatOpenAI  # noqa: E402, F401
    from ai_data_science_team.agents.cloudops_agents import IaCAgent  # noqa: E402, F401

    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = IaCAgent(model=llm)
    agent.invoke_agent(
        user_instructions=(
            "Create a Terraform config for an AWS t3.small EC2 instance named "
            "'web-server' in eu-west-1, and estimate its monthly cost."
        ),
    )
    logger.info(agent.get_ai_message())
    logger.info(agent.get_artifacts())
"""
import logging  # noqa: E402, F401

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional, Sequence  # noqa: E402, F401

from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, TypedDict  # noqa: E402, F401

try:
    from IPython.display import Markdown  # noqa: E402, F401
except ImportError:
    Markdown = None  # type: ignore[assignment,misc]

from langchain.agents import create_agent  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.cloudops import (  # noqa: E402, F401
    estimate_monthly_cost,
    generate_docker_compose_yaml,
    # Containerization
    generate_dockerfile,
    # CI/CD
    generate_github_actions_workflow,
    generate_gitlab_ci_pipeline,
    generate_k8s_manifest,
    list_terraform_providers,
    # IaC
    scaffold_terraform_resource,
    validate_hcl_syntax,
)
from ai_data_science_team.utils.messages import get_tool_call_names  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Tool groups
# ---------------------------------------------------------------------------

_IAC_TOOLS = [
    scaffold_terraform_resource,
    list_terraform_providers,
    estimate_monthly_cost,
    validate_hcl_syntax,
]

_CONTAINER_TOOLS = [
    generate_dockerfile,
    generate_docker_compose_yaml,
    generate_k8s_manifest,
]

_CICD_TOOLS = [
    generate_github_actions_workflow,
    generate_gitlab_ci_pipeline,
]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_IAC_SYSTEM_PROMPT = """You are a senior DevOps engineer and Terraform specialist.
You help teams design, generate, and validate cloud infrastructure using
Infrastructure as Code (IaC) best practices.

Available tools:
- **scaffold_terraform_resource** — Generate a complete Terraform HCL resource block
  for AWS, Azure, or GCP resources (EC2, S3, RDS, Lambda, VMs, etc.).
- **list_terraform_providers** — List common Terraform providers with descriptions.
- **estimate_monthly_cost** — Get an approximate monthly USD cost for a resource type.
- **validate_hcl_syntax** — Validate HCL syntax for structural correctness.

**Recommended workflow:**
1. Use `list_terraform_providers` if the user is unsure which provider to use.
2. Call `scaffold_terraform_resource` for each required resource.
3. Call `estimate_monthly_cost` to provide budget visibility.
4. Call `validate_hcl_syntax` on generated HCL to confirm it is structurally sound.
5. Summarise the generated resources, total estimated cost, and next steps
   (e.g. "run `terraform init && terraform plan`").

Always follow security best practices: use variables for secrets, add tags for
cost allocation, and recommend least-privilege IAM policies."""

_CONTAINER_SYSTEM_PROMPT = """You are a container platform engineer specialising in
Docker and Kubernetes.  You help teams containerise applications and deploy them
to Kubernetes clusters following production best practices.

Available tools:
- **generate_dockerfile** — Create a production-ready Dockerfile for Python, Node,
  Java, Go, or Rust applications.
- **generate_docker_compose_yaml** — Create a docker-compose.yml from a JSON service
  description.
- **generate_k8s_manifest** — Generate Kubernetes YAML manifests (Deployment, Service,
  ConfigMap, Namespace).

**Recommended workflow:**
1. Generate a `Dockerfile` for the application.
2. If local development is needed, generate a `docker-compose.yml`.
3. For production deployment, generate a `Deployment` + `Service` manifest pair.
4. Optionally add a `ConfigMap` for environment-specific configuration.
5. Explain each generated file and recommend next steps
   (e.g. `docker build`, `kubectl apply -f`).

Always follow security best practices: run containers as non-root, use specific
image tags (not ``latest`` in production), set resource requests/limits."""

_CICD_SYSTEM_PROMPT = """You are a CI/CD pipeline engineer with deep expertise in
GitHub Actions and GitLab CI.  You help teams automate their build, test, and
deployment workflows.

Available tools:
- **generate_github_actions_workflow** — Generate a GitHub Actions workflow YAML.
- **generate_gitlab_ci_pipeline** — Generate a .gitlab-ci.yml pipeline definition.

**Recommended workflow:**
1. Determine which CI/CD platform the user needs based on their request.
2. Generate the appropriate pipeline file using the correct tool.
3. Explain each stage and job, and how to activate/trigger the pipeline.
4. Recommend additional steps (e.g. setting secrets in GitHub/GitLab settings,
   caching strategies, matrix builds for multiple Python versions).

Always include quality gates (linting, tests) before build/deploy stages.
Use branch protection to require CI to pass before merging."""


# ===========================================================================
# IaCAgent
# ===========================================================================


class IaCAgent(BaseAgent):
    """Agent that generates Terraform HCL, validates it, and estimates cloud costs.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to the graph's ``invoke``.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for persistence / HITL.
    system_prompt : str, optional
        Override the default IaC system prompt.
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _IAC_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_cloudops_graph(
            agent_name="IaCAgent",
            tools=_IAC_TOOLS,
            **self._params,
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(self, user_instructions: str, **kwargs):
        """Run the IaC agent end-to-end.

        Parameters
        ----------
        user_instructions : str
            Natural-language infrastructure request.
        **kwargs :
            Forwarded to ``self.invoke()``.
        """
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "cloudops_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        """Return the last AI text response."""
        return _extract_ai_message(self.response, markdown)

    def get_artifacts(self) -> Dict[str, Any]:
        """Return accumulated CloudOps artefacts from the last run."""
        return _extract_artifacts(self.response)

    def get_tool_calls(self) -> List[str]:
        """Return tool names invoked in the last run."""
        return _extract_tool_calls(self.response)


# ===========================================================================
# ContainerizationAgent
# ===========================================================================


class ContainerizationAgent(BaseAgent):
    """Agent that generates Dockerfiles, docker-compose files, and K8s manifests.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
    invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    system_prompt : str, optional
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _CONTAINER_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_cloudops_graph(
            agent_name="ContainerizationAgent",
            tools=_CONTAINER_TOOLS,
            **self._params,
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(self, user_instructions: str, **kwargs):
        """Run the containerization agent end-to-end."""
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "cloudops_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        return _extract_ai_message(self.response, markdown)

    def get_artifacts(self) -> Dict[str, Any]:
        return _extract_artifacts(self.response)

    def get_tool_calls(self) -> List[str]:
        return _extract_tool_calls(self.response)


# ===========================================================================
# CICDAgent
# ===========================================================================


class CICDAgent(BaseAgent):
    """Agent that generates GitHub Actions and GitLab CI pipeline YAML files.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
    invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    system_prompt : str, optional
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _CICD_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_cloudops_graph(
            agent_name="CICDAgent",
            tools=_CICD_TOOLS,
            **self._params,
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(self, user_instructions: str, **kwargs):
        """Run the CI/CD agent end-to-end."""
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "cloudops_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        return _extract_ai_message(self.response, markdown)

    def get_artifacts(self) -> Dict[str, Any]:
        return _extract_artifacts(self.response)

    def get_tool_calls(self) -> List[str]:
        return _extract_tool_calls(self.response)


# ===========================================================================
# Shared graph factory
# ===========================================================================


def _build_cloudops_graph(
    agent_name: str,
    tools: list,
    model: Any,
    create_react_agent_kwargs: Dict,
    invoke_react_agent_kwargs: Dict,
    checkpointer: Optional[Checkpointer],
    system_prompt: str,
):
    """Build and compile a CloudOps agent state graph (shared by all three agents)."""

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        cloudops_artifacts: Dict[str, Any]
        tool_calls: List[str]

    react_agent_graph = create_agent(
        model,
        tools=tools,
        state_schema=GraphState,  # type: ignore[arg-type]
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    # ---- nodes ------------------------------------------------------------

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name(agent_name))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        instructions = state.get("user_instructions", "Help with CloudOps tasks.")
        return {"messages": [("user", instructions)]}

    def run_react_agent(state: GraphState):
        logger.info(f"    * RUN REACT TOOL-CALLING AGENT [{agent_name.upper()}]")
        response = react_agent_graph.invoke(state, **invoke_react_agent_kwargs)  # type: ignore[arg-type]
        tool_names = get_tool_call_names(response.get("messages", []))
        return {
            "messages": response.get("messages", []),
            "tool_calls": tool_names,
        }

    def post_process(state: GraphState):
        logger.info("    * POST PROCESS")
        artifacts: Dict[str, Any] = {}
        for msg in state.get("messages", []):
            if hasattr(msg, "artifact") and isinstance(msg.artifact, dict):
                key = str(getattr(msg, "name", "result"))
                artifacts[key] = msg.artifact
        return {"cloudops_artifacts": artifacts}

    # ---- graph wiring -----------------------------------------------------

    builder = StateGraph(GraphState)
    builder.add_node("prepare_messages", prepare_messages)
    builder.add_node("run_react_agent", run_react_agent)
    builder.add_node("post_process", post_process)

    builder.add_edge(START, "prepare_messages")
    builder.add_edge("prepare_messages", "run_react_agent")
    builder.add_edge("run_react_agent", "post_process")
    builder.add_edge("post_process", END)

    return builder.compile(checkpointer=checkpointer, name=agent_name)


# ===========================================================================
# Shared helpers
# ===========================================================================


def _extract_ai_message(response: Optional[Dict], markdown: bool) -> Optional[Any]:
    if not response:
        return None
    for msg in reversed(response.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            text = msg.content
            if markdown and Markdown is not None:
                return Markdown(text)  # type: ignore[return-value]
            return text
    return None


def _extract_artifacts(response: Optional[Dict]) -> Dict[str, Any]:
    if not response:
        return {}
    return response.get("cloudops_artifacts", {})


def _extract_tool_calls(response: Optional[Dict]) -> List[str]:
    if not response:
        return []
    return response.get("tool_calls", [])
