"""Time-Series Agent Ekibi — M13.

Üç ajan:
  TimeSeriesEDAAgent       — trend / mevsimsellik / durağanlık EDA
  ForecastingModelAgent    — ARIMA / Prophet model eğitimi + ileriye dönük tahmin
  ForecastEvaluationAgent  — MAPE / RMSE / MAE / R² metrikleri + yorum

Her ajan `BaseAgent` temelinde, `EDAToolsAgent` ile özdeş mimariyle inşa edilmiştir:
  ``prepare_messages → react_agent (ReAct) → post_process``

Kullanım örneği::

    from langchain_openai import ChatOpenAI
    from ai_data_science_team.ml_agents.time_series_agents import TimeSeriesEDAAgent

    llm    = ChatOpenAI(model="gpt-4o-mini")
    agent  = TimeSeriesEDAAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Bu zaman serisinin mevsimsel yapısını analiz et.",
        data_raw=df,
        date_column="date",
        value_column="revenue",
    )
    logger.info(agent.get_ai_message())
    logger.info(agent.get_artifacts())
"""
from __future__ import annotations



import logging

logger = logging.getLogger(__name__)
from typing import Any, Dict, Optional, Sequence

import pandas as pd
from langchain_core.messages import AIMessage, BaseMessage

try:
    from IPython.display import Markdown  # optional — only needed in notebook contexts
except ImportError:
    Markdown = None  # type: ignore[assignment,misc]

from langchain.agents import create_agent
from langgraph.graph.message import add_messages
from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer
from typing_extensions import Annotated, TypedDict

from ai_data_science_team.templates import BaseAgent
from ai_data_science_team.tools.time_series import (
    autocorrelation_analysis,
    auto_forecast,
    evaluate_forecast,
    seasonal_decompose_ts,
    stationarity_test,
    train_arima,
    train_prophet,
)
from ai_data_science_team.utils.messages import get_tool_call_names
from ai_data_science_team.utils.regex import format_agent_name

# ---------------------------------------------------------------------------
# Tool sets
# ---------------------------------------------------------------------------

_EDA_TOOLS      = [stationarity_test, seasonal_decompose_ts, autocorrelation_analysis]
_FORECAST_TOOLS = [train_arima, train_prophet]
_EVAL_TOOLS     = [evaluate_forecast]
_AUTOFC_TOOLS   = [auto_forecast]

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _series_from_state(state: dict, date_col: str, value_col: str) -> dict:
    """Convert data_raw dict → {dates: [...], values: [...]} for tool calls."""
    data_raw = state.get("data_raw")
    if not data_raw:
        return {}
    df = pd.DataFrame(data_raw)
    result: dict = {}
    if value_col and value_col in df.columns:
        result["values"] = df[value_col].dropna().tolist()
    if date_col and date_col in df.columns:
        result["dates"] = df[date_col].astype(str).tolist()
    return result


def _build_ts_graph(
    agent_name: str,
    tools: list,
    model: Any,
    create_react_agent_kwargs: Dict,
    invoke_react_agent_kwargs: Dict,
    checkpointer: Optional[Checkpointer],
    system_prompt: str,
    artifact_key: str,
    log_tool_calls: bool,
):
    """Generic graph factory shared by all three agents.

    Graph layout:
        START → prepare_messages → react_agent → post_process → END
    """

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        data_raw: dict
        date_column: str
        value_column: str
        ts_artifacts: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=tools,
        state_schema=GraphState,  # type: ignore[arg-type]
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    # -- nodes ---------------------------------------------------------------

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name(agent_name))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions", "Analyze the time series."))]}

    def run_react_agent(state: GraphState):
        logger.info(f"    * RUN REACT TOOL-CALLING AGENT [{agent_name.upper()}]")

        data_info = ""
        data_raw = state.get("data_raw")
        date_col = state.get("date_column", "date")
        value_col = state.get("value_column", "value")

        if data_raw:
            df = pd.DataFrame(data_raw)
            n = len(df)
            cols = ", ".join(df.columns.tolist())
            sample_vals = (
                df[value_col].dropna().head(5).tolist()
                if value_col in df.columns
                else []
            )
            data_info = (
                f"\n\nDataset: {n} rows, columns: [{cols}]"
                f"\nDate column: '{date_col}', Value column: '{value_col}'"
                f"\nFirst 5 values: {sample_vals}"
            )

        full_system = system_prompt + data_info
        base_messages = state.get("messages") or [
            ("user", state.get("user_instructions", "Analyze the time series."))  # type: ignore[list-item]
        ]
        messages = [("system", full_system)] + list(base_messages)  # type: ignore[list-item]

        return react_agent.invoke(  # type: ignore[arg-type]
            {"messages": messages, "data_raw": data_raw},  # type: ignore[arg-type]
            invoke_react_agent_kwargs,  # type: ignore[arg-type]
        )

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING TIME-SERIES RESULTS")

        internal_messages = state.get("messages", [])
        if not internal_messages:
            return {
                "messages": [],
                artifact_key: None,
                "tool_calls": [],
            }

        # Last AI message
        last_ai = None
        for msg in reversed(internal_messages):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                last_ai = AIMessage(
                    content=getattr(msg, "content", ""),
                    name=agent_name,
                )
                break
        if last_ai is None:
            last_ai = AIMessage(
                content=getattr(internal_messages[-1], "content", ""),
                name=agent_name,
            )
        if not getattr(last_ai, "content", "").strip():
            last_ai = AIMessage(
                content="Analysis complete. See artifacts for detailed results.",
                name=agent_name,
            )

        # Collect per-tool artifacts
        artifacts: dict = {}
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            name = getattr(msg, "name", None)
            if art is not None:
                key = name or f"artifact_{len(artifacts) + 1}"
                artifacts[key] = art

        # Append preview to AI message
        if artifacts:
            try:
                last_val = list(artifacts.values())[-1]
                if isinstance(last_val, dict):
                    snippet = pd.DataFrame([last_val]).to_markdown(index=False)
                else:
                    snippet = str(last_val)[:800]
                last_ai = AIMessage(
                    content=f"{last_ai.content}\n\nArtifact preview:\n{snippet}",
                    name=agent_name,
                )
            except Exception:
                pass

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for t in tool_calls:
                logger.info(f"    * Tool called: {t}")

        return {
            "messages": [last_ai],
            "internal_messages": internal_messages,
            artifact_key: artifacts or None,
            "tool_calls": tool_calls,
        }

    # -- compile -------------------------------------------------------------

    wf = StateGraph(GraphState)
    wf.add_node("prepare_messages", prepare_messages)
    wf.add_node("react_agent", react_agent)
    wf.add_node("post_process", post_process)
    wf.add_edge(START, "prepare_messages")
    wf.add_edge("prepare_messages", "react_agent")
    wf.add_edge("react_agent", "post_process")
    wf.add_edge("post_process", END)

    return wf.compile(checkpointer=checkpointer, name=agent_name)


# ---------------------------------------------------------------------------
# Shared mixin for time-series agents
# ---------------------------------------------------------------------------


class _TimeSeriesAgentMixin:
    """Mixin that adds time-series–specific invoke / artifact helpers."""

    _ARTIFACT_KEY: str = "ts_artifacts"
    _compiled_graph: Any  # set by concrete subclass __init__

    # -- invoke --------------------------------------------------------------

    def invoke_agent(
        self,
        user_instructions: str = None,
        data_raw: pd.DataFrame = None,
        date_column: str = "date",
        value_column: str = "value",
        **kwargs,
    ):
        """Synchronously run the agent.

        Parameters
        ----------
        user_instructions : str
            Plain-text instructions passed to the LLM.
        data_raw : pd.DataFrame
            The time-series data (must include ``date_column`` and ``value_column``).
        date_column : str
            Name of the date/timestamp column (default ``"date"``).
        value_column : str
            Name of the numeric target column (default ``"value"``).
        """
        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions or "Analyze the time series.")]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "data_raw": data_raw.to_dict() if data_raw is not None else None,
                "date_column": date_column,
                "value_column": value_column,
            },
            **kwargs,
        )
        self.response = response
        return None

    async def ainvoke_agent(
        self,
        user_instructions: str = None,
        data_raw: pd.DataFrame = None,
        date_column: str = "date",
        value_column: str = "value",
        **kwargs,
    ):
        """Asynchronously run the agent."""
        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions or "Analyze the time series.")]

        response = await self._compiled_graph.ainvoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "data_raw": data_raw.to_dict() if data_raw is not None else None,
                "date_column": date_column,
                "value_column": value_column,
            },
            **kwargs,
        )
        self.response = response
        return None

    def invoke_messages(
        self,
        messages: Sequence[BaseMessage],
        data_raw: pd.DataFrame = None,
        date_column: str = "date",
        value_column: str = "value",
        **kwargs,
    ):
        """Run the agent with an explicit message list (for supervisor/team use)."""
        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": None,
                "data_raw": data_raw.to_dict() if data_raw is not None else None,
                "date_column": date_column,
                "value_column": value_column,
            },
            **kwargs,
        )
        self.response = response
        return None

    async def ainvoke_messages(
        self,
        messages: Sequence[BaseMessage],
        data_raw: pd.DataFrame = None,
        date_column: str = "date",
        value_column: str = "value",
        **kwargs,
    ):
        """Async version of invoke_messages."""
        response = await self._compiled_graph.ainvoke(
            {
                "messages": messages,
                "user_instructions": None,
                "data_raw": data_raw.to_dict() if data_raw is not None else None,
                "date_column": date_column,
                "value_column": value_column,
            },
            **kwargs,
        )
        self.response = response
        return None

    # -- outputs -------------------------------------------------------------

    def get_artifacts(self) -> Optional[dict]:
        """Return the tool artifacts dict from the last run."""
        if not self.response:
            return None
        return self.response.get(self._ARTIFACT_KEY)

    def get_ai_message(self, markdown: bool = False):
        """Return the final AI message content."""
        if not self.response or "messages" not in self.response:
            return None
        msgs = self.response.get("messages", [])
        for msg in reversed(msgs):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai") or getattr(msg, "name", None):
                content = getattr(msg, "content", "")
                return Markdown(content) if markdown else content
        return getattr(msgs[-1], "content", "") if msgs else None

    def get_internal_messages(self, markdown: bool = False):
        """Return raw internal messages from the last run."""
        if not self.response:
            return []
        msgs = self.response.get("internal_messages", [])
        if not markdown:
            return msgs
        pretty = "\n\n".join(
            f"### {getattr(m,'type','MSG').upper()}\n\n{getattr(m,'content','')}"
            for m in msgs
        )
        return Markdown(pretty)

    def get_tool_calls(self) -> list:
        """Return the list of tool names called in the last run."""
        if not self.response:
            return []
        return self.response.get("tool_calls", [])


# ===========================================================================
# Agent 1: TimeSeriesEDAAgent
# ===========================================================================

_TS_EDA_NAME = "time_series_eda_agent"

_TS_EDA_SYSTEM = (
    "You are a time-series EDA specialist. "
    "Given a numeric time series, you must:\n"
    "1. Run a stationarity test (ADF + KPSS) to check if differencing is needed.\n"
    "2. Perform seasonal decomposition to measure trend and seasonal strength.\n"
    "3. Compute ACF / PACF to suggest ARIMA (p, q) parameters.\n"
    "Return a concise, structured summary with your findings and recommendations."
)


class TimeSeriesEDAAgent(_TimeSeriesAgentMixin, BaseAgent):
    """Stationary / seasonality / autocorrelation EDA for time series.

    Parameters
    ----------
    model : LangChain LLM
        The language model that drives the ReAct tool-calling loop.
    create_react_agent_kwargs : dict
        Extra kwargs forwarded to ``create_react_agent``.
    invoke_react_agent_kwargs : dict
        Extra kwargs forwarded to ``agent.invoke()``.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for state persistence.
    log_tool_calls : bool
        Whether to print each tool call to stdout (default True).
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_ts_graph(
            agent_name=_TS_EDA_NAME,
            tools=_EDA_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=_TS_EDA_SYSTEM,
            artifact_key="ts_artifacts",
            log_tool_calls=self._params["log_tool_calls"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()


# ===========================================================================
# Agent 2: ForecastingModelAgent
# ===========================================================================

_FORECAST_NAME = "forecasting_model_agent"

_FORECAST_SYSTEM = (
    "You are a time-series forecasting expert. "
    "Given a numeric time series with dates, you must:\n"
    "1. Choose and fit the best model (ARIMA or Prophet) based on the data characteristics.\n"
    "   - Prefer ARIMA for short, stationary series without strong seasonality.\n"
    "   - Prefer Prophet for longer series with clear seasonality or missing dates.\n"
    "2. Generate a forward forecast for the requested horizon.\n"
    "3. Report in-sample RMSE / MAE so the user can gauge model quality.\n"
    "Return the model type chosen, parameters used, and the forecast table."
)


class ForecastingModelAgent(_TimeSeriesAgentMixin, BaseAgent):
    """Fit ARIMA or Prophet and produce a forward forecast.

    Parameters
    ----------
    model : LangChain LLM
        The language model.
    create_react_agent_kwargs : dict
        Extra kwargs for ``create_react_agent``.
    invoke_react_agent_kwargs : dict
        Extra kwargs for agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer.
    log_tool_calls : bool
        Print tool calls (default True).
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_ts_graph(
            agent_name=_FORECAST_NAME,
            tools=_FORECAST_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=_FORECAST_SYSTEM,
            artifact_key="ts_artifacts",
            log_tool_calls=self._params["log_tool_calls"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()


# ===========================================================================
# Agent 3: ForecastEvaluationAgent
# ===========================================================================

_EVAL_NAME = "forecast_evaluation_agent"

_EVAL_SYSTEM = (
    "You are a forecast evaluation specialist. "
    "Given actual and predicted values, you must:\n"
    "1. Compute MAPE, RMSE, MAE, and R² metrics.\n"
    "2. Assess directional accuracy (did the model predict the direction correctly?).\n"
    "3. Interpret the results: is the model acceptable? What are the weak spots?\n"
    "4. Provide a clear recommendation (deploy / iterate / reconsider).\n"
    "Return a structured evaluation report."
)


class ForecastEvaluationAgent(_TimeSeriesAgentMixin, BaseAgent):
    """Evaluate a forecast by computing MAPE / RMSE / MAE / R².

    Parameters
    ----------
    model : LangChain LLM
        The language model.
    create_react_agent_kwargs : dict
        Extra kwargs for ``create_react_agent``.
    invoke_react_agent_kwargs : dict
        Extra kwargs for agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer.
    log_tool_calls : bool
        Print tool calls (default True).
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_ts_graph(
            agent_name=_EVAL_NAME,
            tools=_EVAL_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=_EVAL_SYSTEM,
            artifact_key="ts_artifacts",
            log_tool_calls=self._params["log_tool_calls"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    # Evaluation agent accepts actual + predicted directly
    def invoke_agent(  # type: ignore[override]
        self,
        user_instructions: str = None,
        data_raw: pd.DataFrame = None,
        actual: Optional[list] = None,
        predicted: Optional[list] = None,
        date_column: str = "date",
        value_column: str = "value",
        **kwargs,
    ):
        """Run evaluation agent.

        Can accept either a DataFrame (``data_raw``) or explicit
        ``actual`` / ``predicted`` lists.  When lists are provided,
        they take precedence over the DataFrame.
        """
        if actual is not None and predicted is not None:
            # Build a minimal DataFrame for state consistency
            data_raw = pd.DataFrame({"actual": actual, "predicted": predicted})
            value_column = "actual"

        messages = kwargs.pop("messages", None)
        if messages is None:
            instr = user_instructions or "Evaluate the forecast accuracy."
            messages = [("user", instr)]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "data_raw": data_raw.to_dict() if data_raw is not None else None,
                "date_column": date_column,
                "value_column": value_column,
            },
            **kwargs,
        )
        self.response = response
        return None


# ===========================================================================
# Agent 4: AutoForecastAgent  (AutoML — races multiple algorithms)
# ===========================================================================

_AUTOFC_NAME = "auto_forecast_agent"

_AUTOFC_SYSTEM = (
    "You are an AutoML time-series forecasting specialist. "
    "Your job is to automatically race multiple forecasting algorithms on a "
    "holdout set and select the winner.\n\n"
    "Workflow:\n"
    "1. Call `auto_forecast` with the user's series, frequency (freq), and "
    "desired forecast horizon (periods_ahead).\n"
    "   - The tool will try: AutoARIMA, AutoETS, AutoTheta, CES, SeasonalNaive, "
    "Naive (via statsforecast if installed, else statsmodels fallback).\n"
    "   - It evaluates each on a walk-forward holdout set.\n"
    "2. Report the **full leaderboard** (all models ranked by holdout RMSE).\n"
    "3. Explain briefly why the winning model outperformed the others (e.g., "
    "strong seasonality favours ETS, unit-root processes favour ARIMA, etc.).\n"
    "4. State the winning model's holdout RMSE / MAE and present its "
    "future forecast values in a clear table or list.\n"
    "5. Note any data-quality caveats (too-short series, irregular frequency, etc.).\n\n"
    "Always use `backend='auto'` unless the user explicitly requests a specific backend."
)


class AutoForecastAgent(_TimeSeriesAgentMixin, BaseAgent):
    """AutoML forecasting agent — races multiple algorithms (AutoARIMA, AutoETS,
    AutoTheta, CES, SeasonalNaive, Naive) and returns the best model plus its
    forward forecast.

    Uses the *statsforecast* library (Nixtla) when installed for speed and
    accuracy; falls back to a statsmodels-based competition otherwise.

    Parameters
    ----------
    model : LangChain LLM
        The language model (e.g. ``ChatOpenAI(model="gpt-4o-mini")``).
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_react_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs used when the graph is invoked.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for conversation memory.
    log_tool_calls : bool
        Print tool call names during execution (default ``True``).

    Quick-start
    -----------
    .. code-block:: python

        from langchain_openai import ChatOpenAI
        from ai_data_science_team.ml_agents import AutoForecastAgent

        llm   = ChatOpenAI(model="gpt-4o-mini")
        agent = AutoForecastAgent(model=llm)
        agent.invoke_agent(
            user_instructions="En iyi modeli seç ve 12 ay sonrasını tahmin et.",
            data_raw=df,
            date_column="date",
            value_column="revenue",
        )
        logger.info(agent.get_ai_message())
        artifacts = agent.get_artifacts()
        # artifacts["auto_forecast"] -> leaderboard + best forecast
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_ts_graph(
            agent_name=_AUTOFC_NAME,
            tools=_AUTOFC_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=_AUTOFC_SYSTEM,
            artifact_key="ts_artifacts",
            log_tool_calls=self._params["log_tool_calls"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()
