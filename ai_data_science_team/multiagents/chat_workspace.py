"""ChatWorkspace — conversational data analysis orchestrator (M21).

The main entry point for the AI Workspace feature. Users upload DataFrames,
then send natural-language messages; the workspace routes each message to the
most appropriate specialist agent and returns a normalized :class:`ChatResponse`.

Architecture decision
---------------------
``ChatWorkspace`` is a **plain Python class**, not a LangGraph agent.

The task is a routing workflow (Anthropic "Building Effective Agents", 2024):

    classify intent → pick agent → invoke → normalize artifact

This pattern is:
* Predictable — fixed execution path, easy to trace.
* Cheap     — no extra LLM round-trip just for orchestration.
* Simple    — fewer abstraction layers = easier debugging.

Existing agents (``PandasDataAnalyst``, ``EDAToolsAgent``, etc.) are reused
as **black-box workers**.  ``ChatWorkspace`` owns session state and
result normalization, nothing else.

Usage
-----
::

    from langchain_openai import ChatOpenAI
    from ai_data_science_team.multiagents import ChatWorkspace

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    ws  = ChatWorkspace(model=llm)

    sid = ws.create_session()
    ws.upload_dataset(sid, "sales", df)

    resp = ws.chat(sid, "en çok satan ürünü göster")
    print(resp.text)
    print(resp.artifact_type)   # "table" | "chart" | "markdown" | None
    print(resp.agent_used)      # "pandas_data_analyst"

    history = ws.get_history(sid)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from langchain_core.messages import AIMessage

from ai_data_science_team.multiagents.chat_router import IntentRouter, RouterDecision
from ai_data_science_team.multiagents.chat_session import (
    ChatMessage,
    ChatSession,
    ChatSessionStore,
)


# ---------------------------------------------------------------------------
# ChatResponse
# ---------------------------------------------------------------------------


@dataclass
class ChatResponse:
    """Normalized response from the AI Workspace.

    Attributes
    ----------
    text : str
        Primary assistant response (plain text or markdown).
    artifact_type : str | None
        One of ``"table"``, ``"chart"``, ``"markdown"``, ``"code"`` or *None*.
    artifact_data : dict | None
        Serialized artifact payload:

        * **table** → ``{"records": [...], "columns": [...]}``
        * **chart** → Plotly figure dict
        * **code**  → ``{"language": "python", "code": "..."}``
    agent_used : str
        Name of the agent that produced this response.
    session_id : str
        Session the response belongs to.
    routing : RouterDecision
        The routing decision that selected ``agent_used``.
    duration_ms : float
        Wall-clock round-trip duration in milliseconds.
    """

    text: str
    artifact_type: Optional[str]
    artifact_data: Optional[Dict[str, Any]]
    agent_used: str
    session_id: str
    routing: RouterDecision
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# ChatWorkspace
# ---------------------------------------------------------------------------


class ChatWorkspace:
    """Session-aware conversational data analysis orchestrator.

    Parameters
    ----------
    model :
        LangChain-compatible LLM used to instantiate specialist agents.
    intent_router : IntentRouter | None
        Custom router.  A default :class:`~.IntentRouter` is created when *None*.
    session_store : ChatSessionStore | None
        Custom session store.  A new in-memory store is created when *None*.
    agent_kwargs : dict | None
        Extra keyword arguments passed to every agent's ``invoke_agent()`` call
        (e.g. ``{"max_retries": 1}`` to speed up tests).
    """

    def __init__(
        self,
        model,
        intent_router: Optional[IntentRouter] = None,
        session_store: Optional[ChatSessionStore] = None,
        agent_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._model = model
        self._router = intent_router or IntentRouter()
        self._store = session_store or ChatSessionStore()
        self._agent_kwargs = agent_kwargs or {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new session and return its id."""
        session = self._store.create(session_id=session_id, metadata=metadata)
        return session.session_id

    def upload_dataset(
        self,
        session_id: str,
        name: str,
        df: pd.DataFrame,
    ) -> None:
        """Upload *df* to the session under *name*."""
        self._store.upload_dataset(session_id, name, df)

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Return the :class:`ChatSession` or *None*."""
        return self._store.get(session_id)

    def get_history(self, session_id: str) -> List[ChatMessage]:
        """Return the message history for *session_id*."""
        return self._store.get_history(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.  Returns *True* if it existed."""
        return self._store.delete(session_id)

    def list_sessions(self) -> List[str]:
        """Return all active session ids."""
        return self._store.list_ids()

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(
        self,
        session_id: str,
        message: str,
        **agent_kwargs,
    ) -> ChatResponse:
        """Route *message* to the best agent and return a :class:`ChatResponse`.

        Steps:

        1. Classify intent via :class:`IntentRouter`.
        2. Retrieve the first uploaded DataFrame from the session (if any).
        3. Invoke the selected specialist agent.
        4. Normalise the agent's response into a :class:`ChatResponse`.
        5. Append user + assistant messages to the session history.

        Parameters
        ----------
        session_id : str
            Must be created via :meth:`create_session`.
        message : str
            The user's natural-language message.
        **agent_kwargs :
            Forwarded to the agent's ``invoke_agent()`` call.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        t0 = time.perf_counter()

        # 1. Route
        decision = self._router.route(message)

        # 2. Session / data
        session = self._store.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        df: Optional[pd.DataFrame] = (
            next(iter(session.datasets.values()), None)
            if session.datasets
            else None
        )

        # 3. Dispatch
        merged_kwargs = {**self._agent_kwargs, **agent_kwargs}
        try:
            text, artifact_type, artifact_data = self._dispatch(
                agent_name=decision.agent_name,
                message=message,
                df=df,
                **merged_kwargs,
            )
        except Exception as exc:
            text = f"⚠ Agent execution error ({decision.agent_name}): {exc}"
            artifact_type = None
            artifact_data = None

        duration_ms = (time.perf_counter() - t0) * 1_000

        response = ChatResponse(
            text=text,
            artifact_type=artifact_type,
            artifact_data=artifact_data,
            agent_used=decision.agent_name,
            session_id=session_id,
            routing=decision,
            duration_ms=duration_ms,
        )

        # 5. Persist
        self._store.add_message(
            session_id, ChatMessage(role="user", content=message)
        )
        self._store.add_message(
            session_id,
            ChatMessage(
                role="assistant",
                content=text,
                artifact=artifact_data,
                agent_used=decision.agent_name,
            ),
        )

        return response

    # ------------------------------------------------------------------
    # Agent dispatch (lazy imports — agents are heavy)
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        agent_name: str,
        message: str,
        df: Optional[pd.DataFrame],
        **kwargs,
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        """Invoke the appropriate agent and return *(text, artifact_type, artifact_data)*."""
        _handlers = {
            "pandas_data_analyst": self._run_pandas_analyst,
            "eda_tools_agent": self._run_eda_agent,
            "sql_data_analyst": self._run_pandas_analyst,  # SQL needs a DB; fall back to pandas when no connection
            "data_cleaning_agent": self._run_data_cleaning,
            "document_parser_agent": self._run_document_parser,
            "api_connector_agent": self._run_api_connector,
            "model_serving_agent": self._run_model_serving,
            "anomaly_detection_agent": self._run_anomaly_detection,
        }
        handler = _handlers.get(agent_name, self._run_pandas_analyst)
        return handler(message=message, df=df, **kwargs)

    # -- Individual agent runners ------------------------------------------

    def _run_pandas_analyst(
        self, message: str, df: Optional[pd.DataFrame], **kwargs
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        from ai_data_science_team.agents import DataWranglingAgent, DataVisualizationAgent
        from ai_data_science_team.multiagents.pandas_data_analyst import PandasDataAnalyst

        agent = PandasDataAnalyst(
            model=self._model,
            data_wrangling_agent=DataWranglingAgent(model=self._model),
            data_visualization_agent=DataVisualizationAgent(model=self._model),
        )
        agent.invoke_agent(
            user_instructions=message,
            data_raw=df if df is not None else pd.DataFrame(),
            **kwargs,
        )
        return _extract_response(agent)

    def _run_eda_agent(
        self, message: str, df: Optional[pd.DataFrame], **kwargs
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent

        agent = EDAToolsAgent(model=self._model)
        agent.invoke_agent(user_instructions=message, data_raw=df, **kwargs)
        return _extract_response(agent)

    def _run_data_cleaning(
        self, message: str, df: Optional[pd.DataFrame], **kwargs
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        from ai_data_science_team.agents import DataCleaningAgent

        agent = DataCleaningAgent(model=self._model)
        agent.invoke_agent(
            user_instructions=message,
            data_raw=df if df is not None else pd.DataFrame(),
            **kwargs,
        )
        return _extract_response(agent)

    def _run_document_parser(
        self, message: str, df: Optional[pd.DataFrame], **kwargs
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        from ai_data_science_team.agents.document_parser_agent import DocumentParserAgent

        agent = DocumentParserAgent(model=self._model)
        agent.invoke_agent(user_instructions=message, **kwargs)
        return _extract_response(agent)

    def _run_api_connector(
        self, message: str, df: Optional[pd.DataFrame], **kwargs
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        from ai_data_science_team.agents.api_connector_agent import APIConnectorAgent

        agent = APIConnectorAgent(model=self._model)
        agent.invoke_agent(user_instructions=message, **kwargs)
        return _extract_response(agent)

    def _run_model_serving(
        self, message: str, df: Optional[pd.DataFrame], **kwargs
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        from ai_data_science_team.agents.model_serving_agent import ModelServingAgent

        agent = ModelServingAgent(model=self._model)
        agent.invoke_agent(user_instructions=message, **kwargs)
        return _extract_response(agent)

    def _run_anomaly_detection(
        self, message: str, df: Optional[pd.DataFrame], **kwargs
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        from ai_data_science_team.agents import AnomalyDetectionAgent

        agent = AnomalyDetectionAgent(model=self._model)
        agent.invoke_agent(
            user_instructions=message,
            data_raw=df if df is not None else pd.DataFrame(),
            **kwargs,
        )
        return _extract_response(agent)


# ---------------------------------------------------------------------------
# Artifact extraction helper (module-level, reusable in tests)
# ---------------------------------------------------------------------------


def _extract_response(
    agent,
) -> Tuple[str, Optional[str], Optional[Dict]]:
    """Extract *(text, artifact_type, artifact_data)* from any agent's response.

    Priority order:
    1. ``data_wrangled`` → table artifact
    2. ``data_cleaned``  → table artifact
    3. ``plotly_graph``  → chart artifact
    4. Last AI message content → plain text, no artifact
    """
    resp: Dict = agent.response or {}

    # ---- text: last AI message ----------------------------------------
    text = ""
    for msg in reversed(resp.get("messages", [])):
        is_ai = isinstance(msg, AIMessage) or getattr(msg, "type", None) == "ai"
        if is_ai:
            text = msg.content if hasattr(msg, "content") else str(msg)
            break
    if not text:
        text = (
            resp.get("answer")
            or resp.get("result")
            or resp.get("output")
            or ""
        )
    if not text:
        text = str(resp) if resp else "No response."

    # ---- artifacts ----------------------------------------------------
    # 1. DataFrame results
    for key in ("data_wrangled", "data_cleaned", "data_raw_transformed"):
        raw = resp.get(key)
        if raw is not None:
            try:
                df_obj = pd.DataFrame.from_dict(raw) if isinstance(raw, dict) else pd.DataFrame(raw)
                return (
                    text,
                    "table",
                    {
                        "records": df_obj.to_dict(orient="records"),
                        "columns": list(df_obj.columns),
                    },
                )
            except Exception:
                pass

    # 2. Plotly chart
    for key in ("plotly_graph", "visualization", "chart"):
        chart = resp.get(key)
        if chart is not None:
            try:
                payload = chart.to_dict() if hasattr(chart, "to_dict") else chart
                return text, "chart", payload
            except Exception:
                pass

    # 3. Generated code artifact
    for key in ("data_wrangler_function", "data_cleaning_function", "code"):
        code = resp.get(key)
        if code and isinstance(code, str):
            return text, "code", {"language": "python", "code": code}

    return text, None, None
