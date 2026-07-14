"""
APIConnectorAgent
=================
A tool-calling agent that makes HTTP REST API calls, handles authentication
(Bearer token / API-key header / Basic auth), parses responses (JSON, CSV,
plain-text) and returns a structured artifact for downstream agents.

Follows the EDAToolsAgent react-agent pattern:
  factory ``make_api_connector_agent()`` → compiled ``StateGraph``
  (prepare_messages → react_agent → post_process)

Supported auth schemes
-----------------------
* ``none``   – unauthenticated requests
* ``bearer`` – ``Authorization: Bearer <token>``
* ``api_key``– arbitrary header name + value  (e.g. ``X-API-Key``)
* ``basic``  – HTTP Basic Auth (username + password)

Supported response formats
---------------------------
* ``json``  – parsed as Python dict / list
* ``csv``   – parsed into a list-of-dicts (pandas)
* ``text``  – raw string
"""

from __future__ import annotations



import logging

logger = logging.getLogger(__name__)
from typing_extensions import (
    Annotated,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
)

import pandas as pd
from IPython.display import Markdown

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import InjectedState
from langgraph.types import Checkpointer

from ai_data_science_team.templates import BaseAgent
from ai_data_science_team.utils.messages import get_tool_call_names
from ai_data_science_team.utils.regex import format_agent_name

AGENT_NAME = "api_connector_agent"

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def call_api(
    url: Annotated[str, InjectedState("url")],
    method: Annotated[str, InjectedState("http_method")],
    auth_scheme: Annotated[str, InjectedState("auth_scheme")],
    auth_credentials: Annotated[Dict, InjectedState("auth_credentials")],
    headers: Annotated[Dict, InjectedState("request_headers")],
    params: Annotated[Dict, InjectedState("query_params")],
    body: Annotated[Dict, InjectedState("request_body")],
    response_format: Annotated[str, InjectedState("response_format")],
    timeout: Annotated[int, InjectedState("timeout")],
) -> Tuple[str, Dict]:
    """
    Tool: call_api
    Description:
        Makes an HTTP request to the specified URL and returns the response
        as a structured artifact (status code, headers, parsed body, latency).

    Parameters:
        url              : Target URL (injected from state).
        method           : HTTP method – GET, POST, PUT, PATCH, DELETE (injected).
        auth_scheme      : Authentication type; one of 'none','bearer','api_key','basic' (injected).
        auth_credentials : Dict of credentials keyed by scheme
                           (e.g. {'token': '...'} for bearer,
                                 {'header': 'X-Key', 'value': '...'} for api_key,
                                 {'username': '...', 'password': '...'} for basic) (injected).
        headers          : Extra request headers (injected).
        params           : URL query parameters (injected).
        body             : Request body for POST/PUT (injected).
        response_format  : Expected response type: 'json', 'csv', 'text' (injected).
        timeout          : Request timeout in seconds (injected).

    Returns:
        Tuple[str, Dict]: text summary + artifact dict with response details.
    """
    logger.info("    * Tool: call_api")

    import time
    import requests as req

    if not url:
        return "Error: URL is required.", {"error": "URL is required."}

    m = (method or "GET").upper()
    scheme = (auth_scheme or "none").lower()
    creds = auth_credentials or {}
    extra_headers = dict(headers or {})
    q_params = dict(params or {})
    payload = dict(body or {})
    fmt = (response_format or "json").lower()
    t_out = int(timeout) if timeout else 30

    # Build auth
    auth_arg = None
    if scheme == "bearer":
        token = creds.get("token", "")
        extra_headers["Authorization"] = f"Bearer {token}"
    elif scheme == "api_key":
        hdr = creds.get("header", "X-API-Key")
        val = creds.get("value", "")
        extra_headers[hdr] = val
    elif scheme == "basic":
        auth_arg = (creds.get("username", ""), creds.get("password", ""))

    try:
        t0 = time.perf_counter()
        resp = req.request(
            method=m,
            url=url,
            headers=extra_headers if extra_headers else None,
            params=q_params if q_params else None,
            json=payload if payload and m in ("POST", "PUT", "PATCH") else None,
            auth=auth_arg,
            timeout=t_out,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        status = resp.status_code
        resp_headers = dict(resp.headers)

        # Parse body
        parsed_body: Any = None
        parse_error: Optional[str] = None
        if fmt == "json":
            try:
                parsed_body = resp.json()
            except Exception as e:
                parse_error = str(e)
                parsed_body = resp.text
        elif fmt == "csv":
            try:
                import io
                df = pd.read_csv(io.StringIO(resp.text))
                parsed_body = df.to_dict(orient="records")
            except Exception as e:
                parse_error = str(e)
                parsed_body = resp.text
        else:
            parsed_body = resp.text

        # Summarise body for content string
        if isinstance(parsed_body, (dict, list)):
            body_preview = str(parsed_body)[:200]
        else:
            body_preview = str(parsed_body)[:200]

        artifact = {
            "url": url,
            "http_method": m,
            "status_code": status,
            "latency_ms": latency_ms,
            "response_headers": resp_headers,
            "response_body": parsed_body,
            "response_format": fmt,
            "ok": status < 400,
        }
        if parse_error:
            artifact["parse_error"] = parse_error

        content = (
            f"API call {m} {url} → HTTP {status} in {latency_ms} ms. "
            f"Body preview: {body_preview}"
        )
        return content, artifact

    except Exception as exc:
        artifact = {
            "url": url,
            "http_method": m,
            "status_code": None,
            "latency_ms": None,
            "response_headers": {},
            "response_body": None,
            "response_format": fmt,
            "ok": False,
            "error": str(exc),
        }
        return f"Request failed: {exc}", artifact


@tool(response_format="content_and_artifact")
def parse_response(
    url: Annotated[str, InjectedState("url")],
    response_format: Annotated[str, InjectedState("response_format")],
    extract_fields: Annotated[List[str], InjectedState("extract_fields")],
    api_results: Annotated[Dict, InjectedState("api_results")],
) -> Tuple[str, Dict]:
    """
    Tool: parse_response
    Description:
        Post-processes the raw API response artifact stored in state.
        Extracts specified fields, converts list-of-dicts to a summary
        table, and returns a clean structured artifact.

    Parameters:
        url            : Original URL – used for metadata (injected).
        response_format: 'json', 'csv', 'text' (injected).
        extract_fields : List of dot-notation field paths to extract from JSON
                         response body (e.g. ['data.items', 'meta.total']) (injected).
        api_results    : Raw artifact from call_api (injected from state).

    Returns:
        Tuple[str, Dict]: summary + parsed artifact.
    """
    logger.info("    * Tool: parse_response")

    if not api_results:
        return "No API results found in state – call call_api first.", {}

    body = api_results.get("response_body")
    fields = extract_fields or []

    extracted: Dict[str, Any] = {}
    if fields and isinstance(body, dict):
        for field_path in fields:
            keys = field_path.split(".")
            val = body
            try:
                for k in keys:
                    if isinstance(val, dict):
                        val = val[k]
                    elif isinstance(val, list) and k.isdigit():
                        val = val[int(k)]
                    else:
                        val = None
                        break
                extracted[field_path] = val
            except (KeyError, IndexError, TypeError):
                extracted[field_path] = None

    # Build records if body is a list
    record_count: Optional[int] = None
    if isinstance(body, list):
        record_count = len(body)
    elif isinstance(body, dict):
        # Try common list keys
        for k in ("data", "results", "items", "records"):
            if isinstance(body.get(k), list):
                record_count = len(body[k])
                break

    artifact = {
        "url": url,
        "status_code": api_results.get("status_code"),
        "ok": api_results.get("ok", False),
        "response_format": response_format,
        "extracted_fields": extracted,
        "record_count": record_count,
        "response_body": body,
    }

    content = (
        f"Response from {url}: status={api_results.get('status_code')}, "
        f"ok={api_results.get('ok', False)}, "
        f"extracted {len(extracted)} field(s)"
        + (f", {record_count} record(s) found" if record_count is not None else "")
        + "."
    )
    return content, artifact


@tool(response_format="content")
def get_api_params(
    url: Annotated[str, InjectedState("url")],
    http_method: Annotated[str, InjectedState("http_method")],
    auth_scheme: Annotated[str, InjectedState("auth_scheme")],
    response_format: Annotated[str, InjectedState("response_format")],
    timeout: Annotated[int, InjectedState("timeout")],
) -> str:
    """
    Tool: get_api_params
    Description:
        Returns a summary of the current API connector configuration.

    Parameters:
        url            : Target URL (injected from state).
        http_method    : HTTP verb (injected from state).
        auth_scheme    : Auth scheme in use (injected from state).
        response_format: Expected response format (injected from state).
        timeout        : Request timeout (injected from state).

    Returns:
        str: Human-readable configuration summary.
    """
    logger.info("    * Tool: get_api_params")
    return (
        f"API Connector config → URL='{url}', method={http_method}, "
        f"auth={auth_scheme}, response_format={response_format}, timeout={timeout}s."
    )


API_TOOLS = [call_api, parse_response, get_api_params]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_api_connector_agent(
    model: Any,
    url: str = "",
    http_method: str = "GET",
    auth_scheme: str = "none",
    auth_credentials: Optional[Dict] = None,
    request_headers: Optional[Dict] = None,
    query_params: Optional[Dict] = None,
    request_body: Optional[Dict] = None,
    response_format: str = "json",
    extract_fields: Optional[List[str]] = None,
    timeout: int = 30,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Creates the compiled LangGraph StateGraph for the APIConnectorAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling, e.g. ChatOpenAI).
    url : str
        Target API endpoint URL.
    http_method : str
        HTTP method: 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'. Default 'GET'.
    auth_scheme : str
        Auth type: 'none', 'bearer', 'api_key', 'basic'. Default 'none'.
    auth_credentials : dict, optional
        Credential dict matching the chosen scheme.
    request_headers : dict, optional
        Additional request headers.
    query_params : dict, optional
        URL query parameters.
    request_body : dict, optional
        JSON request body (for POST/PUT/PATCH).
    response_format : str
        Expected response type: 'json', 'csv', 'text'. Default 'json'.
    extract_fields : list, optional
        Dot-notation field paths to extract from the response body.
    timeout : int
        Request timeout in seconds. Default 30.
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to react-agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer.
    log_tool_calls : bool
        Whether to print tool call names during execution.

    Returns
    -------
    app : langgraph.graph.CompiledStateGraph
    """
    if create_react_agent_kwargs is None:
        create_react_agent_kwargs = {}
    if invoke_react_agent_kwargs is None:
        invoke_react_agent_kwargs = {}

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        # API config
        url: str
        http_method: str
        auth_scheme: str
        auth_credentials: dict
        request_headers: dict
        query_params: dict
        request_body: dict
        response_format: str
        extract_fields: list
        timeout: int
        # Results
        api_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=API_TOOLS,
        state_schema=GraphState,  # type: ignore[arg-type]
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name(AGENT_NAME))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions"))]}

    def run_react_agent(state: GraphState):
        logger.info("    * RUN REACT TOOL-CALLING AGENT FOR API CONNECTOR")
        u = state.get("url", url)
        m = state.get("http_method", http_method)
        logger.info(f"    * {m} {u}")

        system_hint = (
            "You are an API Connector agent. "
            "Call 'call_api' to make the HTTP request, then call 'parse_response' "
            "to extract and structure the response data. "
            "Return a concise summary of what was retrieved."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))  # type: ignore[list-item]
        ]
        messages = [("system", system_hint)] + list(base_messages)  # type: ignore[operator]

        input_payload = {
            "messages": messages,
            "url": state.get("url", url),
            "http_method": state.get("http_method", http_method),
            "auth_scheme": state.get("auth_scheme", auth_scheme),
            "auth_credentials": state.get("auth_credentials") or auth_credentials or {},
            "request_headers": state.get("request_headers") or request_headers or {},
            "query_params": state.get("query_params") or query_params or {},
            "request_body": state.get("request_body") or request_body or {},
            "response_format": state.get("response_format", response_format),
            "extract_fields": state.get("extract_fields") or extract_fields or [],
            "timeout": state.get("timeout", timeout),
            "api_results": state.get("api_results") or {},
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)  # type: ignore[arg-type]

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING API RESPONSE")

        internal_messages = state.get("messages", [])
        if not internal_messages:
            return {"messages": [], "api_results": {}, "tool_calls": []}

        # Find last AI message
        last_ai_message = None
        for msg in reversed(internal_messages):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                last_ai_message = AIMessage(
                    content=getattr(msg, "content", ""),
                    name=AGENT_NAME,
                )
                break
        if last_ai_message is None:
            last_ai_message = AIMessage(
                content=getattr(internal_messages[-1], "content", ""),
                name=AGENT_NAME,
            )
        if not getattr(last_ai_message, "content", "").strip():
            last_ai_message = AIMessage(
                content="API call completed. See api_results for details.",
                name=AGENT_NAME,
            )

        # Collect artifacts from tool messages — smart merge: never overwrite
        # a non-None value with None (prevents stale parse_response calls from
        # wiping valid record_count / response_body set by earlier calls).
        api_artifact: Dict = {}
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            if art is not None and isinstance(art, dict):
                for k, v in art.items():
                    if k not in api_artifact or (api_artifact[k] is None and v is not None):
                        api_artifact[k] = v

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                logger.info(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "api_results": api_artifact,
            "tool_calls": tool_calls,
        }

    workflow = StateGraph(GraphState)
    workflow.add_node("prepare_messages", prepare_messages)
    workflow.add_node("react_agent", react_agent)
    workflow.add_node("post_process", post_process)
    workflow.add_edge(START, "prepare_messages")
    workflow.add_edge("prepare_messages", "react_agent")
    workflow.add_edge("react_agent", "post_process")
    workflow.add_edge("post_process", END)

    app = workflow.compile(
        checkpointer=checkpointer,
        name=AGENT_NAME,
    )
    return app


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class APIConnectorAgent(BaseAgent):
    """
    A tool-calling agent that makes REST API calls, handles authentication,
    and returns structured response data for downstream agent pipelines.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling, e.g. ChatOpenAI).
    url : str
        Target API endpoint URL.
    http_method : str
        HTTP method: 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'. Default 'GET'.
    auth_scheme : str
        Auth type: 'none', 'bearer', 'api_key', 'basic'. Default 'none'.
    auth_credentials : dict, optional
        Credential dict matching the chosen auth scheme.
    request_headers : dict, optional
        Additional HTTP headers to include.
    query_params : dict, optional
        URL query parameters.
    request_body : dict, optional
        JSON request body (for POST/PUT/PATCH).
    response_format : str
        Expected response type: 'json', 'csv', 'text'. Default 'json'.
    extract_fields : list, optional
        Dot-notation field paths to extract from JSON responses.
    timeout : int
        Request timeout in seconds. Default 30.
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to react-agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer.
    log_tool_calls : bool
        Print tool call names when True.

    Examples
    --------
    >>> agent = APIConnectorAgent(model=llm, url="https://api.example.com/data")
    >>> agent.invoke_agent()
    >>> agent.get_status_code()
    >>> agent.get_response_body()
    """

    def __init__(
        self,
        model: Any,
        url: str = "",
        http_method: str = "GET",
        auth_scheme: str = "none",
        auth_credentials: Optional[Dict] = None,
        request_headers: Optional[Dict] = None,
        query_params: Optional[Dict] = None,
        request_body: Optional[Dict] = None,
        response_format: str = "json",
        extract_fields: Optional[List[str]] = None,
        timeout: int = 30,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "url": url,
            "http_method": http_method,
            "auth_scheme": auth_scheme,
            "auth_credentials": auth_credentials or {},
            "request_headers": request_headers or {},
            "query_params": query_params or {},
            "request_body": request_body or {},
            "response_format": response_format,
            "extract_fields": extract_fields or [],
            "timeout": timeout,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_api_connector_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        user_instructions: str = None,
        url: str = None,
        http_method: str = None,
        auth_scheme: str = None,
        auth_credentials: Dict = None,
        request_headers: Dict = None,
        query_params: Dict = None,
        request_body: Dict = None,
        response_format: str = None,
        extract_fields: List[str] = None,
        timeout: int = None,
        **kwargs,
    ):
        """
        Run the API connector agent.

        Parameters
        ----------
        user_instructions : str, optional
            Natural-language description.  Defaults to a generic prompt.
        url : str, optional
            Override the default URL for this call.
        http_method : str, optional
            Override the default HTTP method.
        auth_scheme : str, optional
            Override the default auth scheme.
        auth_credentials : dict, optional
            Credentials for this call.
        request_headers : dict, optional
            Override headers.
        query_params : dict, optional
            Override query parameters.
        request_body : dict, optional
            Override request body.
        response_format : str, optional
            Override expected response format.
        extract_fields : list, optional
            Override field extraction list.
        timeout : int, optional
            Override timeout.
        """
        _url = url or self._params["url"]
        _method = http_method or self._params["http_method"]

        if user_instructions is None:
            user_instructions = (
                f"Call the API at {_url} using HTTP {_method}. "
                "Parse the response and summarise what was returned."
            )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "url": _url,
                "http_method": _method,
                "auth_scheme": auth_scheme or self._params["auth_scheme"],
                "auth_credentials": auth_credentials or self._params["auth_credentials"],
                "request_headers": request_headers or self._params["request_headers"],
                "query_params": query_params or self._params["query_params"],
                "request_body": request_body or self._params["request_body"],
                "response_format": response_format or self._params["response_format"],
                "extract_fields": extract_fields or self._params["extract_fields"],
                "timeout": timeout if timeout is not None else self._params["timeout"],
                "api_results": {},
            },
            **kwargs,
        )
        self.response = response
        return None

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_api_result(self) -> Optional[Dict]:
        """Returns the full API result artifact dictionary."""
        if not self.response:
            return None
        return self.response.get("api_results")

    def get_status_code(self) -> Optional[int]:
        """Returns the HTTP status code of the last response."""
        r = self.get_api_result()
        return r.get("status_code") if r else None

    def get_response_body(self) -> Any:
        """Returns the parsed response body (dict, list, or string)."""
        r = self.get_api_result()
        return r.get("response_body") if r else None

    def get_latency_ms(self) -> Optional[float]:
        """Returns the request latency in milliseconds."""
        r = self.get_api_result()
        return r.get("latency_ms") if r else None

    def is_ok(self) -> Optional[bool]:
        """Returns True if the HTTP status code was < 400."""
        r = self.get_api_result()
        return r.get("ok") if r else None

    def get_extracted_fields(self) -> Optional[Dict]:
        """Returns the dict of extracted dot-notation fields."""
        r = self.get_api_result()
        return r.get("extracted_fields") if r else None

    def get_record_count(self) -> Optional[int]:
        """Returns the number of records in the response (if detectable)."""
        r = self.get_api_result()
        if r is None:
            return None
        if "record_count" in r and r["record_count"] is not None:
            return r["record_count"]
        # Fallback: compute from response_body directly
        body = r.get("response_body")
        if isinstance(body, list):
            return len(body)
        if isinstance(body, dict):
            for k in ("data", "results", "items", "records"):
                if isinstance(body.get(k), list):
                    return len(body[k])
        return None

    def get_response_as_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Converts the response body to a DataFrame if it is a list-of-dicts or
        a dict containing a recognized list key (data/results/items/records).
        Returns None if conversion is not possible.
        """
        body = self.get_response_body()
        if body is None:
            return None
        if isinstance(body, list):
            try:
                return pd.DataFrame(body)
            except Exception:
                return None
        if isinstance(body, dict):
            for k in ("data", "results", "items", "records"):
                if isinstance(body.get(k), list):
                    try:
                        return pd.DataFrame(body[k])
                    except Exception:
                        pass
        return None

    def get_ai_message(self, markdown: bool = False):
        """Returns the last AI message from the agent response."""
        if not self.response or "messages" not in self.response:
            return None
        msgs = self.response.get("messages", [])
        for msg in reversed(msgs):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai", AGENT_NAME):
                content = getattr(msg, "content", "")
                return Markdown(content) if markdown else content
        return None

    def get_tool_calls(self) -> Optional[list]:
        """Returns the list of tool names that were called."""
        if not self.response:
            return None
        return self.response.get("tool_calls")
