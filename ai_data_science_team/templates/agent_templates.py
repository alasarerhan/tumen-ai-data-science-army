import ast
import logging
import re

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command, StreamMode
from langgraph.graph.state import CompiledStateGraph

from langchain_core.runnables import RunnableConfig

import pandas as pd
import sqlalchemy as sql
import json

from typing_extensions import Any, Callable, Dict, Type, Optional, Union, List, Sequence, Annotated

from ai_data_science_team.parsers.parsers import PythonOutputParser
from ai_data_science_team.utils.regex import (
    relocate_imports_inside_function,
    add_comments_to_top,
    remove_consecutive_duplicates,
)
from ai_data_science_team.utils.sandbox import run_code_sandboxed_subprocess  # noqa: E402, F401

from IPython.display import Image, display  # noqa: E402, F401

logger = logging.getLogger(__name__)


def _sanitize_log_message(msg: str) -> str:
    """Sanitize log message to prevent log injection."""
    return re.sub(r'[\n\r\t\x00-\x1f]', ' ', str(msg))[:500]


BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "http", "urllib", "requests",
    "pathlib", "shutil", "ssl", "ftplib", "telnetlib", "webbrowser",
    "pexpect", "psutil", "paramiko", "ctypes", "pickle", "marshal",
    "code", "codeop", "importlib.util", "builtins", "__builtins__",
    "eval", "exec", "compile", "open",
}


def _validate_code_safety(code: str) -> Optional[str]:
    """
    Validate code for potentially dangerous patterns before execution.
    Returns error message if unsafe, None if safe.
    """
    if not code or not isinstance(code, str):
        return "Code must be a non-empty string."
    
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Code has syntax errors: {e}"
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = (alias.name or "").split(".")[0]
                if base in BLOCKED_IMPORTS:
                    return f"Import of '{base}' is blocked for security reasons."
        elif isinstance(node, ast.ImportFrom):
            base = (node.module or "").split(".")[0]
            if base in BLOCKED_IMPORTS:
                return f"Import from '{base}' is blocked for security reasons."
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile", "open", "__import__"):
                    return f"Call to '{node.func.id}()' is blocked for security reasons."
    
    dangerous_patterns = [
        "__import__", "globals()", "locals()", "vars()", "dir()",
        "getattr(", "setattr(", "delattr(", "hasattr(",
        "breakpoint(", "input(",
    ]
    for pattern in dangerous_patterns:
        if pattern in code:
            return f"Potentially dangerous pattern detected: '{pattern}'"
    
    return None


def _validate_read_only_sql_query(sql_text: str) -> Optional[str]:
    """Validate SQL-agent query text before direct execution."""
    if not sql_text or not isinstance(sql_text, str):
        return "SQL query must be a non-empty string."

    stripped = sql_text.strip()
    if not stripped:
        return "SQL query must be a non-empty string."

    lowered = stripped.lower()
    if not lowered.startswith("select"):
        return "Only read-only SELECT queries are allowed."

    forbidden_keywords = [
        "insert", "update", "delete", "drop", "alter", "truncate",
        "create", "replace", "merge", "call", "exec", "execute",
        "grant", "revoke", "into outfile", "into dumpfile",
        "load_file", "benchmark", "sleep", "waitfor", "pg_sleep",
    ]
    for keyword in forbidden_keywords:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return f"Write operations are not allowed; detected forbidden keyword: '{keyword}'."

    for pattern in ("--", "/*", "*/", "#"):
        if pattern in stripped:
            return f"SQL comments are not allowed for security reasons; detected: '{pattern}'."

    semicolon_count = stripped.count(";")
    if semicolon_count > 1:
        return "Multiple SQL statements are not allowed."
    if semicolon_count == 1 and not stripped.endswith(";"):
        return "Semicolon detected in unexpected position."

    if re.search(r"\bunion\b\s+(all\s+)?\bselect\b", lowered):
        return "UNION SELECT is not allowed for security reasons."

    return None


def _extract_sql_query_from_agent_code(code: str, function_name: str) -> Optional[str]:
    """Extract a static sql_query assignment from legacy generated SQL-agent code without executing it."""
    if not code or not function_name:
        return None

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != function_name:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Assign):
                continue
            has_sql_query_target = any(
                isinstance(target, ast.Name) and target.id == "sql_query"
                for target in child.targets
            )
            if has_sql_query_target and isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
                return child.value.value
            if (
                has_sql_query_target
                and isinstance(child.value, ast.Call)
                and isinstance(child.value.func, ast.Attribute)
                and child.value.func.attr == "strip"
                and isinstance(child.value.func.value, ast.Constant)
                and isinstance(child.value.func.value.value, str)
            ):
                return child.value.func.value.value.strip()

    return None


class BaseAgent(CompiledStateGraph):
    """
    A generic base class for agents that interact with compiled state graphs.

    Provides shared functionality for handling parameters, responses, and state
    graph operations.
    """

    def __init__(self, **params):
        """
        Initialize the agent with provided parameters.

        Parameters:
            **params: Arbitrary keyword arguments representing the agent's parameters.
        """
        self._params = params
        self._compiled_graph = self._make_compiled_graph()
        self.response = None
        self.name = self._compiled_graph.name
        self.checkpointer = self._compiled_graph.checkpointer
        self.store = self._compiled_graph.store
        self.output_channels = self._compiled_graph.output_channels
        self.nodes = self._compiled_graph.nodes
        self.stream_mode = self._compiled_graph.stream_mode
        self.builder = self._compiled_graph.builder
        self.channels = self._compiled_graph.channels
        self.input_channels = self._compiled_graph.input_channels
        self._input_schema = self._compiled_graph.input_schema
        self._output_schema = self._compiled_graph.output_schema
        self.debug = self._compiled_graph.debug
        self.interrupt_after_nodes = self._compiled_graph.interrupt_after_nodes
        self.interrupt_before_nodes = self._compiled_graph.interrupt_before_nodes
        self.config = self._compiled_graph.config
    
    @property
    def input_schema(self):
        return self._input_schema
    
    @property
    def output_schema(self):
        return self._output_schema

    def _make_compiled_graph(self):
        """
        Subclasses should override this method to create a specific compiled graph.
        """
        raise NotImplementedError(
            "Subclasses must implement the `_make_compiled_graph` method."
        )

    def update_params(self, **kwargs):
        """
        Update one or more parameters and rebuild the compiled graph.

        Parameters:
            **kwargs: Parameters to update.
        """
        self._params.update(kwargs)
        self._compiled_graph = self._make_compiled_graph()

    def __getattr__(self, name: str):
        """
        Delegate attribute access to the compiled graph if the attribute is not found.

        Parameters:
            name (str): The attribute name.

        Returns:
            Any: The attribute from the compiled graph.
        """
        return getattr(self._compiled_graph, name)

    def invoke(
        self,
        input: Union[dict[str, Any], Any],
        config: Optional[RunnableConfig] = None,
        **kwargs,
    ):
        """
        Wrapper for self._compiled_graph.invoke()

        Parameters:
            input: The input data for the graph. It can be a dictionary or any other type.
            config: Optional. The configuration for the graph run.
            **kwarg: Arguments to pass to self._compiled_graph.invoke()

        Returns:
            Any: The agent's response.
        """
        self.response = self._compiled_graph.invoke(
            input=input, config=config, **kwargs
        )

        if self.response.get("messages"):
            self.response["messages"] = remove_consecutive_duplicates(
                self.response["messages"]
            )

        return self.response

    async def ainvoke(
        self,
        input: Union[dict[str, Any], Any],
        config: Optional[RunnableConfig] = None,
        **kwargs,
    ):
        """
        Wrapper for self._compiled_graph.ainvoke()

        Parameters:
            input: The input data for the graph. It can be a dictionary or any other type.
            config: Optional. The configuration for the graph run.
            **kwarg: Arguments to pass to self._compiled_graph.ainvoke()

        Returns:
            Any: The agent's response.
        """
        self.response = await self._compiled_graph.ainvoke(
            input=input, config=config, **kwargs
        )

        if self.response.get("messages"):
            self.response["messages"] = remove_consecutive_duplicates(
                self.response["messages"]
            )

        return self.response

    def stream(  # type: ignore[override]
        self,
        input: dict[str, Any] | Any,
        config: RunnableConfig | None = None,
        stream_mode: StreamMode | list[StreamMode] | None = None,
        **kwargs,
    ):
        """
        Wrapper for self._compiled_graph.stream()

        Parameters:
            input: The input to the graph.
            config: The configuration to use for the run.
            stream_mode: The mode to stream output, defaults to self.stream_mode.
                Options are 'values', 'updates', and 'debug'.
                values: Emit the current values of the state for each step.
                updates: Emit only the updates to the state for each step.
                    Output is a dict with the node name as key and the updated values as value.
                debug: Emit debug events for each step.
            **kwarg: Arguments to pass to self._compiled_graph.stream()

        Returns:
            Any: The agent's response.
        """
        self.response = self._compiled_graph.stream(
            input=input, config=config, stream_mode=stream_mode, **kwargs
        )

        if self.response.get("messages"):
            self.response["messages"] = remove_consecutive_duplicates(
                self.response["messages"]
            )

        return self.response

    async def astream(  # type: ignore[override]
        self,
        input: dict[str, Any] | Any,
        config: RunnableConfig | None = None,
        stream_mode: StreamMode | list[StreamMode] | None = None,
        **kwargs,
    ):
        """
        Wrapper for self._compiled_graph.astream()

        Parameters:
            input: The input to the graph.
            config: The configuration to use for the run.
            stream_mode: The mode to stream output, defaults to self.stream_mode.
                Options are 'values', 'updates', and 'debug'.
                values: Emit the current values of the state for each step.
                updates: Emit only the updates to the state for each step.
                    Output is a dict with the node name as key and the updated values as value.
                debug: Emit debug events for each step.
            **kwarg: Arguments to pass to self._compiled_graph.astream()

        Returns:
            Any: The agent's response.
        """
        self.response = await self._compiled_graph.astream(
            input=input, config=config, stream_mode=stream_mode, **kwargs
        )

        if self.response.get("messages"):
            self.response["messages"] = remove_consecutive_duplicates(
                self.response["messages"]
            )

        return self.response

    def get_state_keys(self):
        """
        Returns a list of keys that the state graph response contains.

        Returns:
            list: A list of keys in the response.
        """
        return list(self.get_output_jsonschema()["properties"].keys())

    def get_state(self, config, *, subgraphs=False):
        """
        Returns the state of the agent.
        """
        return self._compiled_graph.get_state(config, subgraphs=subgraphs)

    def get_state_history(self, config, *, filter=None, before=None, limit=None):
        """
        Returns the state history of the agent.
        """
        return self._compiled_graph.get_state_history(
            config, filter=filter, before=before, limit=limit
        )

    def update_state(self, config, values, as_node=None):
        """
        Updates the state of the agent.
        """
        return self._compiled_graph.update_state(config, values, as_node)

    def _get_messages(self, user_instructions: Optional[str] = None) -> List[BaseMessage]:
        """
        Build messages list from user instructions.
        
        Subclasses can override this to customize message construction.
        """
        from langchain_core.messages import HumanMessage  # noqa: E402, F401
        if user_instructions:
            return [HumanMessage(content=user_instructions)]
        return []

    def invoke_agent(
        self,
        data_raw: Optional[pd.DataFrame] = None,
        user_instructions: Optional[str] = None,
        max_retries: int = 3,
        retry_count: int = 0,
        **kwargs,
    ):
        """
        Common invoke method for data processing agents.
        
        Parameters:
        ----------
        data_raw : pd.DataFrame, optional
            The input data to process.
        user_instructions : str, optional
            Instructions for the agent.
        max_retries : int
            Maximum number of retry attempts on error.
        retry_count : int
            Current retry count.
        **kwargs : dict
            Additional agent-specific parameters.
            
        Returns:
        -------
        dict
            The agent response.
        """
        messages = self._get_messages(user_instructions)
        
        state_input = {
            "messages": messages,
            "user_instructions": user_instructions,
            "max_retries": max_retries,
            "retry_count": retry_count,
            **kwargs,
        }
        
        if data_raw is not None:
            state_input["data_raw"] = data_raw
        
        return self.invoke(state_input)

    async def ainvoke_agent(
        self,
        data_raw: Optional[pd.DataFrame] = None,
        user_instructions: Optional[str] = None,
        max_retries: int = 3,
        retry_count: int = 0,
        **kwargs,
    ):
        """
        Async version of invoke_agent.
        """
        messages = self._get_messages(user_instructions)
        
        state_input = {
            "messages": messages,
            "user_instructions": user_instructions,
            "max_retries": max_retries,
            "retry_count": retry_count,
            **kwargs,
        }
        
        if data_raw is not None:
            state_input["data_raw"] = data_raw
        
        return await self.ainvoke(state_input)

    def get_response(self) -> Optional[Dict[str, Any]]:
        """
        Returns the response generated by the agent.

        Returns:
            Any: The agent's response.
        """
        if self.response and self.response.get("messages"):
            self.response["messages"] = remove_consecutive_duplicates(
                self.response["messages"]
            )

        return self.response

    def get_state_properties(self) -> Dict[str, Any]:
        """
        Returns detailed properties of the state graph response.

        Returns:
            dict: The properties of the response.
        """
        return self.get_output_jsonschema()["properties"]

    def get_workflow_summary(self, markdown: bool = False) -> Optional[str]:
        """
        Retrieves the agent's workflow summary.

        Parameters:
            markdown : bool
                Whether to return as Markdown.

        Returns:
            str or None
                The workflow summary.
        """
        if self.response and self.response.get("messages"):
            try:
                from ai_data_science_team.utils.regex import get_generic_summary  # noqa: E402, F401
                summary = get_generic_summary(
                    json.loads(self.response.get("messages")[-1].content)
                )
                if markdown:
                    from IPython.display import Markdown  # noqa: E402, F401
                    return Markdown(summary)
                return summary
            except Exception:
                return None
        return None

    def get_log_summary(self, markdown: bool = False) -> Optional[str]:
        """
        Retrieves a summary of logged operations.

        Parameters:
            markdown : bool
                Whether to return as Markdown.

        Returns:
            str or None
                The log summary.
        """
        return None

    def show(self, xray: int = 0) -> None:
        """
        Displays the agent's state graph as a Mermaid diagram.

        Parameters:
            xray (int): If set to 1, displays subgraph levels. Defaults to 0.
        """
        display(Image(self.get_graph(xray=xray).draw_mermaid_png()))


def create_coding_agent_graph(
    GraphState: Type,
    node_functions: Dict[str, Callable],
    recommended_steps_node_name: str,
    create_code_node_name: str,
    execute_code_node_name: str,
    fix_code_node_name: str,
    explain_code_node_name: str,
    error_key: str,
    max_retries_key: str = "max_retries",
    retry_count_key: str = "retry_count",
    human_in_the_loop: bool = False,
    human_review_node_name: str = "human_review",
    checkpointer: Optional[Callable] = None,
    bypass_recommended_steps: bool = False,
    bypass_explain_code: bool = False,
    agent_name: str = "coding_agent",
):
    """
    Creates a generic agent graph using the provided node functions and node names.

    Parameters
    ----------
    GraphState : Type
        The TypedDict or class used as state for the workflow.
    node_functions : dict
        A dictionary mapping node names to their respective functions.
        Example: {
            "recommend_cleaning_steps": recommend_cleaning_steps,
            "human_review": human_review,
            "create_data_cleaner_code": create_data_cleaner_code,
            "execute_data_cleaner_code": execute_data_cleaner_code,
            "fix_data_cleaner_code": fix_data_cleaner_code,
            "explain_data_cleaner_code": explain_data_cleaner_code
        }
    recommended_steps_node_name : str
        The node name that recommends steps.
    create_code_node_name : str
        The node name that creates the code.
    execute_code_node_name : str
        The node name that executes the generated code.
    fix_code_node_name : str
        The node name that fixes code if errors occur.
    explain_code_node_name : str
        The node name that explains the final code.
    error_key : str
        The state key used to check for errors.
    max_retries_key : str, optional
        The state key used for the maximum number of retries.
    retry_count_key : str, optional
        The state key for the current retry count.
    human_in_the_loop : bool, optional
        Whether to include a human review step.
    human_review_node_name : str, optional
        The node name for human review if human_in_the_loop is True.
    checkpointer : callable, optional
        A checkpointer callable if desired.
    bypass_recommended_steps : bool, optional
        Whether to skip the recommended steps node.
    bypass_explain_code : bool, optional
        Whether to skip the final explain code node.
    name : str, optional
        The name of the agent graph.

    Returns
    -------
    app : langchain.graphs.StateGraph
        The compiled workflow application.
    """

    workflow = StateGraph(GraphState)

    # * NODES

    # Always add create, execute, and fix nodes
    workflow.add_node(create_code_node_name, node_functions[create_code_node_name])
    workflow.add_node(execute_code_node_name, node_functions[execute_code_node_name])
    workflow.add_node(fix_code_node_name, node_functions[fix_code_node_name])

    # Conditionally add the recommended-steps node
    if not bypass_recommended_steps:
        workflow.add_node(
            recommended_steps_node_name, node_functions[recommended_steps_node_name]
        )

    # Conditionally add the human review node
    if human_in_the_loop:
        workflow.add_node(
            human_review_node_name, node_functions[human_review_node_name]
        )

    # Conditionally add the explanation node
    if not bypass_explain_code:
        workflow.add_node(
            explain_code_node_name, node_functions[explain_code_node_name]
        )

    # * EDGES

    # Set the entry point
    entry_point = (
        create_code_node_name
        if bypass_recommended_steps
        else recommended_steps_node_name
    )

    workflow.set_entry_point(entry_point)

    if not bypass_recommended_steps:
        workflow.add_edge(recommended_steps_node_name, create_code_node_name)

    workflow.add_edge(create_code_node_name, execute_code_node_name)
    workflow.add_edge(fix_code_node_name, execute_code_node_name)

    # Define a helper to check if we have an error & can still retry
    def error_and_can_retry(state):
        return (
            state.get(error_key) is not None
            and state.get(retry_count_key) is not None
            and state.get(max_retries_key) is not None
            and state[retry_count_key] < state[max_retries_key]
        )

    # If human in the loop, add a branch for human review
    if human_in_the_loop:
        workflow.add_conditional_edges(
            execute_code_node_name,
            lambda s: "fix_code" if error_and_can_retry(s) else "human_review",
            {
                "human_review": human_review_node_name,
                "fix_code": fix_code_node_name,
            },
        )
    else:
        # If no human review, the next node is fix_code if error, else explain_code.
        if not bypass_explain_code:
            workflow.add_conditional_edges(
                execute_code_node_name,
                lambda s: "fix_code" if error_and_can_retry(s) else "explain_code",
                {
                    "fix_code": fix_code_node_name,
                    "explain_code": explain_code_node_name,
                },
            )
        else:
            workflow.add_conditional_edges(
                execute_code_node_name,
                lambda s: "fix_code" if error_and_can_retry(s) else "END",
                {
                    "fix_code": fix_code_node_name,
                    "END": END,
                },
            )

    if not bypass_explain_code:
        workflow.add_edge(explain_code_node_name, END)

    # Finally, compile
    app = workflow.compile(
        checkpointer=checkpointer,  # type: ignore[arg-type]
        name=agent_name,
    )

    return app


def node_func_human_review(
    state: Any,
    prompt_text: str,
    yes_goto: str,
    no_goto: str,
    user_instructions_key: str = "user_instructions",
    recommended_steps_key: str = "recommended_steps",
    code_snippet_key: str = "code_snippet",
    code_type: str = "python",
) -> Command[str]:
    """
    A generic function to handle human review steps.

    Parameters
    ----------
    state : GraphState
        The current GraphState.
    prompt_text : str
        The text to display to the user before their input.
    yes_goto : str
        The node to go to if the user confirms (answers "yes").
    no_goto : str
        The node to go to if the user suggests modifications.
    user_instructions_key : str, optional
        The key in the state to store user instructions.
    recommended_steps_key : str, optional
        The key in the state to store recommended steps.
    code_snippet_key : str, optional
        The key in the state to store the code snippet.
    code_type : str, optional
        The type of code snippet to display (e.g., "python").

    Returns
    -------
    Command[str]
        A Command object directing the next state and updates to the state.
    """
    print("    * HUMAN REVIEW")

    code_markdown = f"```{code_type}\n" + state.get(code_snippet_key) + "\n```"

    # Display instructions and get user response
    user_input = interrupt(
        value=prompt_text.format(
            steps=state.get(recommended_steps_key, "") + "\n\n" + code_markdown
        )
    )

    # Decide next steps based on user input
    if user_input.strip().lower() == "yes":
        goto = yes_goto
        update = {}
    else:
        goto = no_goto
        modifications = (
            "User Has Requested Modifications To Previous Code: \n" + user_input
        )
        if state.get(user_instructions_key) is None:
            update = {
                user_instructions_key: modifications
                + "\n\nPrevious Code:\n"
                + code_markdown
            }
        else:
            update = {
                user_instructions_key: state.get(user_instructions_key)
                + modifications
                + "\n\nPrevious Code:\n"
                + code_markdown
            }

    return Command(goto=goto, update=update)


def node_func_execute_agent_code_on_data(
    state: Any,
    data_key: str,
    code_snippet_key: str,
    result_key: str,
    error_key: str,
    agent_function_name: str,
    pre_processing: Optional[Callable[[Any], Any]] = None,
    post_processing: Optional[Callable[[Any], Any]] = None,
    error_message_prefix: str = "An error occurred during agent execution: ",
) -> Dict[str, Any]:
    """
    Execute a generic agent code defined in a code snippet retrieved from the state on input data and return the result.

    Parameters
    ----------
    state : Any
        A state object that supports `get(key: str)` method to retrieve values.
    data_key : str
        The key in the state used to retrieve the input data.
    code_snippet_key : str
        The key in the state used to retrieve the Python code snippet defining the agent function.
    result_key : str
        The key in the state used to store the result of the agent function.
    error_key : str
        The key in the state used to store the error message if any.
    agent_function_name : str
        The name of the function (e.g., 'data_cleaner') expected to be defined in the code snippet.
    pre_processing : Callable[[Any], Any], optional
        A function to preprocess the data before passing it to the agent function.
        This might be used to convert raw data into a DataFrame or otherwise transform it.
        If not provided, a default approach will be used if data is a dict.
    post_processing : Callable[[Any], Any], optional
        A function to postprocess the output of the agent function before returning it.
    error_message_prefix : str, optional
        A prefix or full message to use in the error output if an exception occurs.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the result and/or error messages. Keys are arbitrary,
        but typically include something like "result" or "error".
    """

    print("    * EXECUTING AGENT CODE")

    data = state.get(data_key)
    agent_code = state.get(code_snippet_key)

    code_validation_error = _validate_code_safety(agent_code)
    if code_validation_error:
        logger.warning(f"Code validation failed: {_sanitize_log_message(code_validation_error)}")
        return {result_key: None, error_key: f"{error_message_prefix}{code_validation_error}"}

    try:
        if pre_processing is None:
            if isinstance(data, dict):
                df_data = data
            elif isinstance(data, list):
                df_data = data
            else:
                return {result_key: None, error_key: f"{error_message_prefix}Data is not a dictionary or list and no pre_processing function was provided."}
        else:
            df_data = pre_processing(data)
    except Exception as e:
        return {result_key: None, error_key: f"{error_message_prefix}{str(e)}"}

    data_format = "dataframe_list" if isinstance(df_data, list) else "dataframe"
    
    result, exec_error = run_code_sandboxed_subprocess(
        code_snippet=agent_code,
        function_name=agent_function_name,
        data=df_data,
        timeout=60,
        memory_limit_mb=512,
        data_format=data_format,
    )

    if exec_error:
        logger.error(f"Code execution failed: {_sanitize_log_message(exec_error)}")
        return {result_key: None, error_key: f"{error_message_prefix}{exec_error}"}

    if post_processing is not None and result is not None:
        try:
            result = post_processing(result)
        except Exception as e:
            return {result_key: None, error_key: f"{error_message_prefix}{str(e)}"}

    output = {result_key: result, error_key: None}
    return output


def node_func_execute_agent_from_sql_connection(
    state: Any,
    connection: Any,
    code_snippet_key: str,
    result_key: str,
    error_key: str,
    agent_function_name: str,
    post_processing: Optional[Callable[[Any], Any]] = None,
    error_message_prefix: str = "An error occurred during agent execution: ",
) -> Dict[str, Any]:
    """
    Execute a generic agent code defined in a code snippet retrieved from the state on a SQLAlchemy connection object
    and return the result.

    Parameters
    ----------
    state : Any
        A state object that supports `get(key: str)` method to retrieve values.
    connection : str
        The SQLAlchemy connection object to use for executing the agent function.
    code_snippet_key : str
        The key in the state used to retrieve the Python code snippet defining the agent function.
    result_key : str
        The key in the state used to store the result of the agent function.
    error_key : str
        The key in the state used to store the error message if any.
    agent_function_name : str
        The name of the function (e.g., 'sql_database_agent') expected to be defined in the code snippet.
    post_processing : Callable[[Any], Any], optional
        A function to postprocess the output of the agent function before returning it.
    error_message_prefix : str, optional
        A prefix or full message to use in the error output if an exception occurs.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the result and/or error messages. Keys are arbitrary,
        but typically include something like "result" or "error".
    """

    print("    * EXECUTING AGENT CODE ON SQL CONNECTION")

    agent_code = state.get(code_snippet_key)

    if connection is None:
        raise ValueError("Connection object not found.")

    sql_query = state.get("sql_query_code")
    if not sql_query:
        sql_query = _extract_sql_query_from_agent_code(agent_code, agent_function_name)
    if not sql_query:
        return {
            result_key: None,
            error_key: (
                f"{error_message_prefix}SQL query text not found. "
                "Dynamic SQL-agent Python execution is disabled."
            ),
        }

    validation_error = _validate_read_only_sql_query(sql_query)
    if validation_error:
        logger.warning("SQL validation failed: %s", _sanitize_log_message(validation_error))
        return {result_key: None, error_key: f"{error_message_prefix}{validation_error}"}

    agent_error = None
    result = None
    is_engine = isinstance(connection, sql.engine.base.Engine)
    conn = connection.connect() if is_engine else connection
    try:
        result = pd.read_sql(sql_query, conn)

        if post_processing is not None:
            result = post_processing(result)
    except Exception as e:
        agent_error = f"{error_message_prefix}{str(e)}"
    finally:
        if is_engine:
            conn.close()

    output = {result_key: result, error_key: agent_error}
    return output


def node_func_fix_agent_code(
    state: Any,
    code_snippet_key: str,
    error_key: str,
    llm: Any,
    prompt_template: str,
    agent_name: str,
    retry_count_key: str = "retry_count",
    log: bool = False,
    file_path: str = "logs/agent_function.py",
    function_name: str = "agent_function",
) -> dict:
    """
    Generic function to fix a given piece of agent code using an LLM and a prompt template.

    Parameters
    ----------
    state : Any
        A state object that supports `get(key: str)` method to retrieve values.
    code_snippet_key : str
        The key in the state used to retrieve the broken code snippet.
    error_key : str
        The key in the state used to retrieve the related error message.
    llm : Any
        The language model or pipeline capable of receiving prompts and returning responses.
        It should support a call like `(llm | PythonOutputParser()).invoke(prompt)`.
    prompt_template : str
        A string template for the prompt that will be sent to the LLM. It should contain
        placeholders `{code_snippet}` and `{error}` which will be formatted with the actual values.
    agent_name : str
        The name of the agent being fixed. This is used to add comments to the top of the code.
    retry_count_key : str, optional
        The key in the state that tracks how many times we've retried fixing the code.
    log : bool, optional
        Whether to log the returned code to a file.
    file_path : str, optional
        The path to the file where the code will be logged.
    function_name : str, optional
        The name of the function in the code snippet that will be fixed.

    Returns
    -------
    dict
        A dictionary containing updated code, cleared error, and incremented retry count.
    """
    print("    * FIX AGENT CODE")
    print("      retry_count:" + str(state.get(retry_count_key)))

    # Retrieve the code snippet and the error from the state
    code_snippet = state.get(code_snippet_key)
    error_message = state.get(error_key)

    # Format the prompt with the code snippet and the error
    prompt = prompt_template.format(
        code_snippet=code_snippet,
        error=error_message,
        function_name=function_name,
        user_instructions=state.get("user_instructions"),
        recommended_steps=state.get("recommended_steps"),
    )

    # Execute the prompt with the LLM
    response = (llm | PythonOutputParser()).invoke(prompt)

    response = relocate_imports_inside_function(response)
    response = add_comments_to_top(response, agent_name=agent_name)

    # Log the response if requested
    if log:
        with open(file_path, "w") as file:
            file.write(response)
            print(f"      File saved to: {file_path}")

    # Return updated results
    return {
        code_snippet_key: response,
        error_key: None,
        retry_count_key: state.get(retry_count_key) + 1,
    }


def node_func_explain_agent_code(
    state: Any,
    code_snippet_key: str,
    result_key: str,
    error_key: str,
    llm: Any,
    role: str,
    explanation_prompt_template: str,
    success_prefix: str = "# Agent Explanation:\n\n",
    error_message: str = "The agent encountered an error during execution and cannot be explained.",
) -> Dict[str, Any]:
    """
    Generic function to explain what a given agent code snippet does.

    Parameters
    ----------
    state : Any
        A state object that supports `get(key: str)` to retrieve values.
    code_snippet_key : str
        The key in `state` where the agent code snippet is stored.
    result_key : str
        The key in `state` where the LLM's explanation is stored. Typically this is "messages".
    error_key : str
        The key in `state` where any error messages related to the code snippet are stored.
    llm : Any
        The language model used to explain the code. Should support `.invoke(prompt)`.
    role : str
        The role of the agent explaining the code snippet. Examples: "Data Scientist", "Data Engineer", etc.
    explanation_prompt_template : str
        A prompt template that can be used to explain the code. It should contain a placeholder
        for inserting the agent code snippet. For example:

        "Explain the steps performed by this agent code in a succinct manner:\n\n{code}"

    success_prefix : str, optional
        A prefix to add before the LLM's explanation, helping format the final message.
    error_message : str, optional
        Message to return if the agent code snippet cannot be explained due to an error.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing one key "messages", which is a list of messages (e.g., AIMessage)
        describing the explanation or the error.
    """
    print("    * EXPLAIN AGENT CODE")

    # Check if there's an error associated with the code
    agent_error = state.get(error_key)
    if agent_error is None:
        # Retrieve the code snippet
        code_snippet = state.get(code_snippet_key)

        # Format the prompt by inserting the code snippet
        prompt = explanation_prompt_template.format(code=code_snippet)

        # Invoke the LLM to get an explanation
        response = llm.invoke(prompt)

        # Prepare the success message
        message = AIMessage(content=f"{success_prefix}{response.content}", role=role)
        return {"messages": [message]}
    else:
        # Return an error message if there was a problem with the code
        message = AIMessage(content=error_message)
        return {result_key: [message]}


def node_func_report_agent_outputs(
    state: Dict[str, Any],
    keys_to_include: List[str],
    result_key: str,
    role: str,
    custom_title: str = "Agent Output Summary",
) -> Dict[str, Any]:
    """
    Gathers relevant data directly from the state (filtered by `keys_to_include`)
    and returns them as a structured message in `state[result_key]`.

    No LLM is used.

    Parameters
    ----------
    state : Dict[str, Any]
        The current state dictionary holding all agent variables.
    keys_to_include : List[str]
        The list of keys in `state` to include in the output.
    result_key : str
        The key in `state` under which we'll store the final structured message.
    role : str
        The role that will be used in the final AIMessage (e.g., "DataCleaningAgent").
    custom_title : str, optional
        A title or heading for your report. Defaults to "Agent Output Summary".
    """
    print("    * REPORT AGENT OUTPUTS")

    final_report = {"report_title": custom_title}

    for key in keys_to_include:
        final_report[key] = state.get(key, f"<{key}_not_found_in_state>")

    # Wrap it in a list of messages (like the current "messages" pattern).
    # You can serialize this dictionary as JSON or just cast it to string.
    return {
        result_key: [AIMessage(content=json.dumps(final_report, indent=2), role=role)]
    }


def create_react_agent_graph(
    model: Any,
    tools: List[str],
    system_prompt: str = "",
    max_iterations: int = 10,
    GraphState: Optional[Type] = None,
    checkpointer: Optional[Any] = None,
    agent_name: str = "react_agent",
    prepare_state: Optional[Callable[[Dict], Dict]] = None,
    post_process: Optional[Callable[[Dict], Dict]] = None,
):
    """Create a ReAct-style agent graph that dynamically calls tools from ToolRegistry.

    The ReAct (Reasoning + Acting) pattern allows the LLM to:
    1. Think about what tool to use
    2. Execute the tool
    3. Observe the result
    4. Repeat until done

    Parameters
    ----------
    model : Any
        The language model (must support tool calling).
    tools : List[str]
        List of tool names registered in ToolRegistry.
    system_prompt : str, optional
        System prompt for the agent.
    max_iterations : int, optional
        Maximum number of tool-calling iterations.
    GraphState : Type, optional
        Custom state schema. If None, uses default ReActState.
    checkpointer : Any, optional
        Checkpointer for state persistence.
    agent_name : str, optional
        Name for the compiled graph.
    prepare_state : Callable, optional
        Function to prepare initial state from input.
    post_process : Callable, optional
        Function to post-process final state.

    Returns
    -------
    CompiledStateGraph
        A compiled LangGraph that implements the ReAct pattern.

    Example
    -------
    ::

        from ai_data_science_team.templates import create_react_agent_graph  # noqa: E402, F401
        from ai_data_science_team.tool_registry import ToolRegistry  # noqa: E402, F401

        # Tools must be registered first
        from ai_data_science_team.tools.anomaly import *  # noqa: E402, F401

        agent = create_react_agent_graph(
            model=ChatOpenAI(model="gpt-4"),
            tools=["isolation_forest_detect", "lof_detect", "ensemble_detect"],
            system_prompt="You are an anomaly detection expert...",
            max_iterations=10,
        )

        result = agent.invoke({
            "messages": [HumanMessage(content="Detect anomalies in this data")],
            "data_raw": df.to_dict(),
        })
    """
    from langchain_core.messages import SystemMessage, ToolMessage  # noqa: E402, F401
    from langgraph.graph import StateGraph, START, END  # noqa: E402, F401
    from langgraph.graph.message import add_messages  # noqa: E402, F401
    from typing_extensions import TypedDict  # noqa: E402, F401

    if GraphState is None:
        class ReActState(TypedDict):
            messages: Annotated[Sequence[BaseMessage], add_messages]
            iteration: int
            data_raw: Optional[dict]
            result: Optional[Any]
            error: Optional[str]
        GraphState = ReActState

    tool_defs = []
    tool_executors = {}
    for tool_name in tools:
        try:
            defn, executor = __import__(
                "ai_data_science_team.tool_registry", fromlist=["ToolRegistry"]
            ).ToolRegistry.get(tool_name)
            tool_defs.append(defn)
            tool_executors[tool_name] = executor
        except KeyError:
            logger.warning(f"Tool '{tool_name}' not found in registry, skipping")

    if not tool_defs:
        raise ValueError("No valid tools found in ToolRegistry")

    def think_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("    * THINK (selecting tool)")
        messages = list(state.get("messages", []))
        if system_prompt and (not messages or not isinstance(messages[0], SystemMessage)):
            messages = [SystemMessage(content=system_prompt)] + messages

        openai_tools = [t.to_openai_tool() for t in tool_defs]
        response = model.invoke(messages, tools=openai_tools)
        return {"messages": [response], "iteration": state.get("iteration", 0)}

    def act_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("    * ACT (executing tool)")
        last_message = state["messages"][-1]
        new_messages = []

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return state

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", tool_name)

            if tool_name in tool_executors:
                try:
                    if "data_raw" in tool_args and tool_args["data_raw"] is None:
                        tool_args["data_raw"] = state.get("data_raw")
                    result = tool_executors[tool_name](**tool_args)
                    result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                    new_messages.append(
                        ToolMessage(content=result_str, tool_call_id=tool_id)
                    )
                except Exception as e:
                    logger.error(f"Tool '{tool_name}' execution failed: {e}")
                    new_messages.append(
                        ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id)
                    )
            else:
                new_messages.append(
                    ToolMessage(content=f"Tool '{tool_name}' not available", tool_call_id=tool_id)
                )

        return {"messages": new_messages}

    def should_continue(state: Dict[str, Any]) -> str:
        last = state["messages"][-1]
        if not hasattr(last, "tool_calls") or not last.tool_calls:
            return "end"
        if state.get("iteration", 0) >= max_iterations:
            logger.warning(f"Max iterations ({max_iterations}) reached")
            return "end"
        return "act"

    def prepare_node(state: Dict[str, Any]) -> Dict[str, Any]:
        if prepare_state:
            return prepare_state(state)
        return {"iteration": 0}

    def finalize_node(state: Dict[str, Any]) -> Dict[str, Any]:
        if post_process:
            return post_process(state)
        last = state["messages"][-1]
        if hasattr(last, "content"):
            return {"result": last.content}
        return {}

    workflow = StateGraph(GraphState)

    workflow.add_node("prepare", prepare_node)
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "think")
    workflow.add_conditional_edges("think", should_continue, {"act": "act", "end": "finalize"})
    workflow.add_edge("act", "think")
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer, name=agent_name)
