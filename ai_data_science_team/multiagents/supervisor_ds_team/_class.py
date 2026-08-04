from __future__ import annotations

"""``SupervisorDSTeam`` OO wrapper.

This module contains only the ``SupervisorDSTeam`` class — an OO
façade over the compiled graph produced by ``make_supervisor_ds_team``.
The class mirrors the pattern used by other agents: holds a compiled
graph, exposes message-first helpers, and keeps the latest response.

Split out from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.
"""

from typing import Any, Optional, Sequence  # noqa: E402, F401

from IPython.display import Markdown  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401

from ai_data_science_team.multiagents.supervisor_ds_team import (  # noqa: E402, F401
    make_supervisor_ds_team,
)


class SupervisorDSTeam:
    """OO wrapper for the supervisor-led data science team.

    Mirrors the pattern used by other agents: holds a compiled graph,
    exposes message-first helpers, and keeps the latest response.
    """

    def __init__(
        self,
        model: Any,
        data_loader_agent,
        data_wrangling_agent,
        data_cleaning_agent,
        eda_tools_agent,
        data_visualization_agent,
        sql_database_agent,
        feature_engineering_agent,
        h2o_ml_agent,
        mlflow_tools_agent,
        model_evaluation_agent,
        workflow_planner_agent=None,
        checkpointer: Optional[Checkpointer] = None,
        temperature: float = 1.0,
    ):
        self._params = {
            "model": model,
            "workflow_planner_agent": workflow_planner_agent,
            "data_loader_agent": data_loader_agent,
            "data_wrangling_agent": data_wrangling_agent,
            "data_cleaning_agent": data_cleaning_agent,
            "eda_tools_agent": eda_tools_agent,
            "data_visualization_agent": data_visualization_agent,
            "sql_database_agent": sql_database_agent,
            "feature_engineering_agent": feature_engineering_agent,
            "h2o_ml_agent": h2o_ml_agent,
            "mlflow_tools_agent": mlflow_tools_agent,
            "model_evaluation_agent": model_evaluation_agent,
            "checkpointer": checkpointer,
            "temperature": temperature,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response: Optional[dict] = None

    def _make_compiled_graph(self):
        self.response = None
        return make_supervisor_ds_team(
            model=self._params["model"],
            workflow_planner_agent=self._params["workflow_planner_agent"],
            data_loader_agent=self._params["data_loader_agent"],
            data_wrangling_agent=self._params["data_wrangling_agent"],
            data_cleaning_agent=self._params["data_cleaning_agent"],
            eda_tools_agent=self._params["eda_tools_agent"],
            data_visualization_agent=self._params["data_visualization_agent"],
            sql_database_agent=self._params["sql_database_agent"],
            feature_engineering_agent=self._params["feature_engineering_agent"],
            h2o_ml_agent=self._params["h2o_ml_agent"],
            mlflow_tools_agent=self._params["mlflow_tools_agent"],
            model_evaluation_agent=self._params["model_evaluation_agent"],
            checkpointer=self._params["checkpointer"],
            temperature=self._params["temperature"],
        )

    def update_params(self, **kwargs):
        """Update parameters (e.g., swap sub-agents or model) and rebuild
        the graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_messages(
        self,
        messages: Sequence[BaseMessage],
        artifacts: Optional[dict] = None,
        **kwargs,
    ):
        """Invoke the team with a message list (recommended for
        supervisor/teams)."""
        self.response = self._compiled_graph.invoke(
            {"messages": messages, "artifacts": artifacts or {}},
            **kwargs,
        )
        return None

    async def ainvoke_messages(
        self,
        messages: Sequence[BaseMessage],
        artifacts: Optional[dict] = None,
        **kwargs,
    ):
        """Async version of invoke_messages."""
        self.response = await self._compiled_graph.ainvoke(
            {"messages": messages, "artifacts": artifacts or {}},
            **kwargs,
        )
        return None

    def invoke_agent(self, user_instructions: str, artifacts: Optional[dict] = None, **kwargs):
        """Convenience wrapper for a single human prompt."""
        msg = HumanMessage(content=user_instructions)
        return self.invoke_messages(messages=[msg], artifacts=artifacts, **kwargs)

    async def ainvoke_agent(
        self, user_instructions: str, artifacts: Optional[dict] = None, **kwargs
    ):
        msg = HumanMessage(content=user_instructions)
        return await self.ainvoke_messages(messages=[msg], artifacts=artifacts, **kwargs)

    def invoke(self, input: dict, **kwargs):
        """Generic invoke passthrough (for backward compatibility)."""
        self.response = self._compiled_graph.invoke(input, **kwargs)
        return self.response

    async def ainvoke(self, input: dict, **kwargs):
        self.response = await self._compiled_graph.ainvoke(input, **kwargs)
        return self.response

    def get_ai_message(self, markdown: bool = False):
        """Return the last assistant/ai message."""
        if not self.response or "messages" not in self.response:
            return None
        last_ai = None
        for msg in reversed(self.response.get("messages", [])):
            if isinstance(msg, AIMessage) or getattr(msg, "role", None) in (
                "assistant",
                "ai",
            ):
                last_ai = msg
                break
        if last_ai is None:
            return None
        content = getattr(last_ai, "content", "")
        return Markdown(content) if markdown else content

    def get_artifacts(self):
        """Return aggregated artifacts dict from the supervisor state."""
        if self.response:
            return self.response.get("artifacts")
        return None

    def show(self, xray: int = 0):
        """Displays the supervisor team's state graph as a Mermaid
        diagram."""
        try:
            from IPython.display import Image, display  # noqa: E402, F401

            display(Image(self._compiled_graph.get_graph(xray=xray).draw_mermaid_png()))
        except Exception:
            return None

    def _repr_mimebundle_(self, *args, **kwargs):
        """Jupyter/IPython rich display: render the supervisor graph as
        a Mermaid PNG."""
        try:
            png = self._compiled_graph.get_graph(xray=0).draw_mermaid_png()
            return {"image/png": png, "text/plain": repr(self)}
        except Exception:
            return {"text/plain": repr(self)}
