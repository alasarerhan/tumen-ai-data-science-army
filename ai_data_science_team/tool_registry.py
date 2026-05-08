"""ToolRegistry - Central registry for all agent tools (OwnPilot pattern).

This module provides a unified tool management system following the OwnPilot pattern:
- Tool definitions are separate from executors
- Tools are organized by namespace (core., custom., plugin., skill., mcp.)
- Meta-tool proxy pattern: only 4 meta-tools exposed to LLM
- Dynamic tool discovery via registry search

Design
------
* **Class-level storage**: no instance needed; the registry is a singleton.
* **Metadata only**: no live tool instances are stored.
* **Thread-safe reads**: writes (register/clear) are protected by a lock.

Usage
-----
::

    from ai_data_science_team.tool_registry import ToolRegistry, ToolDefinition

    # Register a tool
    ToolRegistry.register(
        name="scatter_plot",
        definition=ToolDefinition(
            name="scatter_plot",
            description="Create a scatter plot from two numeric columns",
            parameters={
                "x": {"type": "string", "description": "X-axis column name"},
                "y": {"type": "string", "description": "Y-axis column name"},
            },
            namespace="core.visualization",
            capabilities=["visualization", "scatter", "numeric"],
        ),
        executor=scatter_plot_executor,
    )

    # Search for tools
    tools = ToolRegistry.search(capability="visualization")

    # Get tool for execution
    tool_def, executor = ToolRegistry.get("scatter_plot")
    result = executor(data=df, x="age", y="income")
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type
from enum import Enum


class ToolNamespace(str, Enum):
    """Tool namespace prefixes for origin tracking."""
    CORE = "core"
    CUSTOM = "custom"
    PLUGIN = "plugin"
    SKILL = "skill"
    MCP = "mcp"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    type: str
    description: str = ""
    required: bool = True
    default: Any = None
    enum: List[str] | None = None


@dataclass
class ToolDefinition:
    """Metadata record for a single registered tool.

    Parameters
    ----------
    name : str
        Unique identifier used throughout the platform (e.g. ``"scatter_plot"``).
    description : str
        Human-readable description of what the tool does.
    parameters : dict
        JSON-Schema-like dict describing expected parameters.
    returns : str
        Description of what the tool returns.
    namespace : str
        Namespace prefix (e.g. ``"core.visualization"``).
    capabilities : list[str]
        List of capability tags (e.g. ``["visualization", "scatter"]``).
    cost_tier : str
        Approximate cost level: ``"low"`` / ``"medium"`` / ``"high"``.
    tags : list[str]
        Arbitrary labels for grouping/filtering.
    version : str
        Semantic version of this tool.
    examples : list[dict]
        Example usages for documentation.
    """

    name: str
    description: str = ""
    parameters: Dict[str, ToolParameter] = field(default_factory=dict)
    returns: str = ""
    namespace: str = "core"
    capabilities: List[str] = field(default_factory=list)
    cost_tier: str = "low"
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                k: {"type": v.type, "description": v.description, "required": v.required}
                for k, v in self.parameters.items()
            },
            "returns": self.returns,
            "namespace": self.namespace,
            "capabilities": self.capabilities,
            "cost_tier": self.cost_tier,
            "tags": self.tags,
            "version": self.version,
        }

    def to_openai_tool(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []
        for param_name, param in self.parameters.items():
            properties[param_name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param_name]["enum"] = param.enum
            if param.required:
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


ToolExecutor = Callable[..., Any]


class ToolRegistry:
    """Class-level singleton registry for all agent tools.

    All read/write operations are exposed as class methods so callers never
    need to create an instance.

    The registry stores:
    - Tool definitions (metadata)
    - Tool executors (callable functions)
    - Namespace mappings

    Meta-tool pattern:
    - Only 4 meta-tools are exposed to the LLM: search_tools, get_tool_help, use_tool, batch_use_tool
    - All actual tools are discovered dynamically via the registry
    """

    _tools: Dict[str, ToolDefinition] = {}
    _executors: Dict[str, ToolExecutor] = {}
    _namespaces: Dict[str, List[str]] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def register(
        cls,
        name: str,
        definition: ToolDefinition,
        executor: ToolExecutor,
        overwrite: bool = True,
    ) -> ToolDefinition:
        """Register a tool and return its definition.

        Parameters
        ----------
        name : str
            Unique tool name. Existing entry is overwritten when
            *overwrite* is True (default); raises ``ValueError`` otherwise.
        definition : ToolDefinition
            The tool metadata.
        executor : Callable
            The function that executes the tool.
        overwrite : bool
            If False, raises ``ValueError`` when *name* is already registered.
        """
        with cls._lock:
            if not overwrite and name in cls._tools:
                raise ValueError(
                    f"Tool '{name}' is already registered. "
                    "Pass overwrite=True to replace it."
                )
            cls._tools[name] = definition
            cls._executors[name] = executor

            namespace = definition.namespace or "core"
            if namespace not in cls._namespaces:
                cls._namespaces[namespace] = []
            if name not in cls._namespaces[namespace]:
                cls._namespaces[namespace].append(name)

        return definition

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove a tool from the registry. Silent if not found."""
        with cls._lock:
            if name in cls._tools:
                namespace = cls._tools[name].namespace or "core"
                if namespace in cls._namespaces and name in cls._namespaces[namespace]:
                    cls._namespaces[namespace].remove(name)
                cls._tools.pop(name, None)
                cls._executors.pop(name, None)

    @classmethod
    def clear(cls) -> None:
        """Remove all registrations (primarily useful in tests)."""
        with cls._lock:
            cls._tools.clear()
            cls._executors.clear()
            cls._namespaces.clear()

    @classmethod
    def get(cls, name: str) -> tuple[ToolDefinition, ToolExecutor]:
        """Return the definition and executor for *name*.

        Raises
        ------
        KeyError
            If *name* is not registered.
        """
        with cls._lock:
            if name not in cls._tools:
                raise KeyError(
                    f"Tool '{name}' is not registered. "
                    f"Available: {sorted(cls._tools.keys())}"
                )
            return cls._tools[name], cls._executors[name]

    @classmethod
    def get_or_none(cls, name: str) -> tuple[ToolDefinition, ToolExecutor] | None:
        """Return the definition and executor or *None* if not registered."""
        with cls._lock:
            if name not in cls._tools:
                return None
            return cls._tools[name], cls._executors[name]

    @classmethod
    def search(
        cls,
        capability: str | None = None,
        tag: str | None = None,
        namespace: str | None = None,
        cost_tier: str | None = None,
    ) -> List[ToolDefinition]:
        """Return tools matching all supplied filters (AND semantics).

        Parameters
        ----------
        capability : str | None
            Filter to tools whose ``capabilities`` list contains this value.
        tag : str | None
            Filter to tools whose ``tags`` list contains this value.
        namespace : str | None
            Filter by namespace prefix.
        cost_tier : str | None
            Filter by cost tier (``"low"`` / ``"medium"`` / ``"high"``).
        """
        with cls._lock:
            results = list(cls._tools.values())

        if capability:
            results = [t for t in results if capability in t.capabilities]
        if tag:
            results = [t for t in results if tag in t.tags]
        if namespace:
            results = [t for t in results if t.namespace.startswith(namespace)]
        if cost_tier:
            results = [t for t in results if t.cost_tier == cost_tier]

        return sorted(results, key=lambda t: t.name)

    @classmethod
    def list_all(cls) -> List[ToolDefinition]:
        """Return all registered tools sorted by name."""
        with cls._lock:
            return sorted(cls._tools.values(), key=lambda t: t.name)

    @classmethod
    def names(cls) -> List[str]:
        """Return a sorted list of all registered tool names."""
        with cls._lock:
            return sorted(cls._tools.keys())

    @classmethod
    def by_namespace(cls, namespace: str) -> List[ToolDefinition]:
        """Return all tools in a namespace."""
        with cls._lock:
            tool_names = cls._namespaces.get(namespace, [])
            return [cls._tools[n] for n in tool_names if n in cls._tools]

    @classmethod
    def size(cls) -> int:
        """Return the number of registered tools."""
        with cls._lock:
            return len(cls._tools)

    @classmethod
    def to_catalog(cls) -> List[Dict[str, Any]]:
        """Return a JSON-serialisable list of all tool metadata dicts."""
        return [t.to_dict() for t in cls.list_all()]

    @classmethod
    def to_openai_tools(cls) -> List[Dict[str, Any]]:
        """Return all tools in OpenAI function calling format."""
        return [t.to_openai_tool() for t in cls.list_all()]


def register_tool(
    name: str,
    description: str = "",
    parameters: Dict[str, ToolParameter] | None = None,
    returns: str = "",
    namespace: str = "core",
    capabilities: List[str] | None = None,
    cost_tier: str = "low",
    tags: List[str] | None = None,
) -> Callable[[ToolExecutor], ToolExecutor]:
    """Decorator to register a function as a tool.

    Usage
    -----
    ::

        @register_tool(
            name="scatter_plot",
            description="Create a scatter plot",
            parameters={
                "x": ToolParameter(type="string", description="X column"),
                "y": ToolParameter(type="string", description="Y column"),
            },
            namespace="core.visualization",
            capabilities=["visualization", "scatter"],
        )
        def scatter_plot(data, x, y):
            import plotly.express as px
            return px.scatter(data, x=x, y=y)
    """
    def decorator(func: ToolExecutor) -> ToolExecutor:
        definition = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or {},
            returns=returns,
            namespace=namespace,
            capabilities=capabilities or [],
            cost_tier=cost_tier,
            tags=tags or [],
        )
        ToolRegistry.register(name, definition, func)
        return func
    return decorator


__all__ = [
    "ToolRegistry",
    "ToolDefinition",
    "ToolParameter",
    "ToolNamespace",
    "ToolExecutor",
    "register_tool",
]
