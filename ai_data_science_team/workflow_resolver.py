"""WorkflowResolver — scenario detection and WorkflowSpec resolution (M22).

Three execution scenarios
--------------------------
1. **Dynamic**    (``"dynamic"``)   — natural-language goal → LLM generates a
   :data:`WorkflowSpec` → RuntimeEngine manages the execution.
2. **Supervised** (``"supervised"``) — caller supplies a :data:`WorkflowSpec`
   → RuntimeEngine manages the execution; caller is the design author.
3. **Manual**     (``"manual"``)    — caller supplies a :data:`WorkflowSpec`
   AND manages execution themselves; RuntimeEngine provides only
   infrastructure (retry, checkpointing, logging).

WorkflowSpec schema
-------------------
::

    {
      "name": str,           # short workflow name (required)
      "description": str,    # what this workflow accomplishes (optional)
      "steps": [             # ordered list of steps (required, non-empty)
        {
          "id": str,         # unique within the workflow (required)
          "agent": str,      # AgentRegistry.name (required)
          "instruction": str,# natural-language task for the agent (required)
          "depends_on": [],  # list of step ids that must finish first
          "fallbacks": [],   # ordered list of fallback agent names
        },
        ...
      ]
    }

Usage
-----
::

    from ai_data_science_team.workflow_resolver import WorkflowResolver
    from ai_data_science_team.agent_registry import AgentRegistry

    resolver = WorkflowResolver(
        model=llm,
        registry_catalog=AgentRegistry.to_catalog(),
    )

    result = resolver.resolve(user_goal="Load sales.csv and produce an EDA report")
    # result = {"scenario": "dynamic", "spec": {...}, "errors": []}

    result2 = resolver.resolve(workflow_spec=my_spec)
    # result2 = {"scenario": "supervised", "spec": my_spec, "errors": []}
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage


# ---------------------------------------------------------------------------
# WorkflowSpec helpers
# ---------------------------------------------------------------------------


def build_step(
    step_id: str,
    agent: str,
    instruction: str,
    depends_on: Optional[List[str]] = None,
    fallbacks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convenience constructor for a single WorkflowSpec step dict."""
    return {
        "id": step_id,
        "agent": agent,
        "instruction": instruction,
        "depends_on": depends_on or [],
        "fallbacks": fallbacks or [],
    }


def build_spec(
    name: str,
    steps: List[Dict[str, Any]],
    description: str = "",
) -> Dict[str, Any]:
    """Convenience constructor for a complete WorkflowSpec dict."""
    return {
        "name": name,
        "description": description,
        "steps": steps,
    }


def validate_spec(spec: Dict[str, Any]) -> List[str]:
    """Validate a WorkflowSpec dict and return a list of error messages.

    Returns an empty list when the spec is valid.

    Parameters
    ----------
    spec : dict
        A candidate WorkflowSpec dict.

    Returns
    -------
    list[str]
        Human-readable error messages; empty list means the spec is valid.
    """
    if not isinstance(spec, dict):
        return ["Spec must be a dict."]

    errors: List[str] = []

    if not spec.get("name"):
        errors.append("Missing required field: 'name'.")

    steps = spec.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        errors.append("'steps' must be a non-empty list.")
        return errors  # Cannot validate steps without a valid list

    step_ids: List[str] = []
    for i, step in enumerate(steps):
        label = f"Step {i} (id={step.get('id', '?')})"
        if not step.get("id"):
            errors.append(f"{label}: missing required field 'id'.")
        else:
            if step["id"] in step_ids:
                errors.append(f"{label}: duplicate step id '{step['id']}'.")
            step_ids.append(step["id"])
        if not step.get("agent"):
            errors.append(f"{label}: missing required field 'agent'.")
        if not step.get("instruction"):
            errors.append(f"{label}: missing required field 'instruction'.")

    # Validate depends_on references
    ids_set = set(step_ids)
    for step in steps:
        sid = step.get("id", "?")
        for dep in step.get("depends_on", []):
            if dep not in ids_set:
                errors.append(
                    f"Step '{sid}': depends_on references unknown step id '{dep}'."
                )

    return errors


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse a JSON dict from *text*, tolerating markdown fences."""
    if not text:
        return None

    # Direct parse
    try:
        parsed = json.loads(text.strip())
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Extract from markdown code fence
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # Extract first JSON object in the text
    obj_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# WorkflowResolver
# ---------------------------------------------------------------------------

_SPEC_GENERATION_PROMPT = """\
You are a workflow planning assistant for a data science platform.
Given the user's goal and the list of available agents, produce a WorkflowSpec
JSON object that describes an ordered pipeline of steps.

Available agents:
{catalog}

WorkflowSpec schema:
{{
  "name": "<short workflow name>",
  "description": "<what this workflow does>",
  "steps": [
    {{
      "id": "<unique_step_id>",
      "agent": "<agent name>",
      "instruction": "<natural-language task for the agent>",
      "depends_on": [],
      "fallbacks": []
    }}
  ]
}}

Rules:
- If the catalog is non-empty, prefer agents listed there (match the name exactly).
- If the catalog is empty, you may invent descriptive PascalCase agent names that
  fit the data science domain (e.g. DataLoaderAgent, DataCleaningAgent, EDAAgent,
  DataWranglingAgent, DataVisualizationAgent, FeatureEngineeringAgent).
- Each step id must be unique within the workflow (e.g. "load", "clean", "eda").
- List steps in dependency order.
- Prefer a minimal plan (2-4 steps) that satisfies the user request.
- "steps" MUST contain at least one element.
- Return ONLY valid JSON — absolutely no markdown fences, no prose, no comments.

User goal: {user_goal}
"""


class WorkflowResolver:
    """Determines the execution scenario and resolves or generates a WorkflowSpec.

    Parameters
    ----------
    model : BaseChatModel | None
        LLM used **only** in the *Dynamic* scenario to generate a WorkflowSpec
        from a natural-language goal.  Not required for Supervised/Manual.
    registry_catalog : list[dict] | None
        Output of ``AgentRegistry.to_catalog()`` — injected into the LLM
        prompt so the model knows which agents are available.
        If None, an empty catalog is used (limits dynamic generation quality).
    """

    DYNAMIC = "dynamic"
    SUPERVISED = "supervised"
    MANUAL = "manual"

    def __init__(
        self,
        model: Optional[Any] = None,
        registry_catalog: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._model = model
        self._catalog = registry_catalog or []

    # ------------------------------------------------------------------ public

    def resolve(
        self,
        *,
        user_goal: Optional[str] = None,
        workflow_spec: Optional[Dict[str, Any]] = None,
        scenario: Optional[str] = None,
        managed_by_user: bool = False,
    ) -> Dict[str, Any]:
        """Determine the scenario and return a resolved spec.

        Parameters
        ----------
        user_goal : str | None
            Natural-language task description (triggers Dynamic scenario).
        workflow_spec : dict | None
            Pre-built spec (triggers Supervised or Manual scenario).
        scenario : str | None
            Explicitly override auto-detection
            (``"dynamic"`` / ``"supervised"`` / ``"manual"``).
        managed_by_user : bool
            When True and *workflow_spec* is provided, forces the Manual
            scenario (user manages execution).

        Returns
        -------
        dict
            ``{"scenario": str, "spec": dict, "errors": list[str]}``
        """
        # --- scenario detection ---
        if scenario:
            resolved_scenario = scenario
        elif workflow_spec and managed_by_user:
            resolved_scenario = self.MANUAL
        elif workflow_spec:
            resolved_scenario = self.SUPERVISED
        elif user_goal:
            resolved_scenario = self.DYNAMIC
        else:
            resolved_scenario = self.MANUAL

        # --- spec resolution ---
        if resolved_scenario == self.DYNAMIC:
            spec = self._generate_spec(user_goal or "")
        elif resolved_scenario in (self.SUPERVISED, self.MANUAL):
            spec = workflow_spec or {}
        else:
            spec = {}

        errors = validate_spec(spec) if spec else ["No WorkflowSpec could be resolved."]

        return {
            "scenario": resolved_scenario,
            "spec": spec,
            "errors": errors,
        }

    # ------------------------------------------------------------------ private

    def _generate_spec(self, user_goal: str) -> Dict[str, Any]:
        """Call the LLM to produce a WorkflowSpec from a user goal string."""
        if not self._model or not user_goal.strip():
            return {}

        catalog_json = json.dumps(self._catalog, indent=2)[:4000]
        prompt = _SPEC_GENERATION_PROMPT.format(
            catalog=catalog_json,
            user_goal=user_goal,
        )

        try:
            result = self._model.invoke([HumanMessage(content=prompt)])
            content = getattr(result, "content", "") or ""
            spec = _safe_json_parse(content)
            return spec or {}
        except Exception:  # noqa: BLE001
            return {}

    # ------------------------------------------------------------------ utilities

    @staticmethod
    def validate(spec: Dict[str, Any]) -> List[str]:
        """Convenience static access to :func:`validate_spec`."""
        return validate_spec(spec)

    @staticmethod
    def build_step(
        step_id: str,
        agent: str,
        instruction: str,
        depends_on: Optional[List[str]] = None,
        fallbacks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build a single step dict."""
        return build_step(step_id, agent, instruction, depends_on, fallbacks)

    @staticmethod
    def build_spec(
        name: str,
        steps: List[Dict[str, Any]],
        description: str = "",
    ) -> Dict[str, Any]:
        """Build a complete WorkflowSpec dict."""
        return build_spec(name, steps, description)


__all__ = [
    "WorkflowResolver",
    "validate_spec",
    "build_step",
    "build_spec",
]
